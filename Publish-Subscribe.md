# 发布 / 订阅

**(using the Pika Python client)**

## 本章节教程重点介绍的内容

在上一篇教程中，我们创建了工作队列。工作队列背后的假设是每个任务只能传递给一个工作人员。
在这一部分，我们将做一些完全不同的事情 - 我们会向多个消费者传递信息。这种模式被称为“发布/订阅”。

为了说明这种模式，我们将建立一个简单的日志系统。它将包含两个程序 - 第一个将发送日志消息，第二个将接收并打印它们。

在我们的日志系统中，接收程序的每个运行副本都会收到消息。这样我们就可以运行一个接收器并将日志指向磁盘; 同时我们将能够运行另一个接收器并在屏幕上查看日志。

一般来说，发布的日志消息将以广播的形式发给所有的接收者。

### 交易所

在本教程的前几部分中，我们发送消息并从队列中接收消息。现在是时候在rabbitmq中引入完整的消息传递模型。

让我们快速回顾一下前面教程中的内容：
  - 生产者是发送消息的用户的应用程序。
  - 队列是存储消息的缓冲器。
  - 消费者是接收消息的用户的应用程序。

RabbitMQ中的消息传递模型的核心思想是生产者永远不会将任何消息直接发送到队列中。实际上，生产者通常甚至不知道邮件是否会被传送到任何队列中。

相反，生产者只能发送消息给交易所。交换是一件非常简单的事情。一方面它接收来自生产者的消息，另一方则推动他们排队。
交易所必须知道如何处理收到的消息。是否应该附加到特定队列？它应该附加到许多队列中吗？或者它应该被丢弃。这些规则由交换类型定义 (exchange type)。

![](https://img.vim-cn.com/dd/438322ed5919e11b186d4089aef47de7f719a6.png)

有几种可用的交换类型： direct, topic, header 和 fanout。我们将关注最后一个 - fanout。让我们创建该类型的交换，并将其称为logs：

```python
channel.exchange_declare(exchange='logs',
                         exchange_type='fanout')
```

fanout交换非常简单。正如你可能从名字中猜出的那样，它只是将收到的所有消息广播到它所知道的所有队列中。这正是我们logger所需要的。

现在，我们可以发布到我们的指定交易所：

```python
channel.basic_publish(exchange='logs',
                      routing_key='',
                      body=message)
```

### 临时队列

正如你以前可能记得我们正在使用具有指定名称的队列(还记得*hello*和*task_queue*吗？)。能够命名队列对我们至关重要 - 我们需要将工作人员指向同一队列。
当你想在生产者和消费者之间分享队列时，给队列一个名字是很重要的。

但是，我们的记录器并非如此。我们希望听到所有日志消息，而不仅仅是其中的一部分。我们也只对目前流动的消息感兴趣，而不是旧消息。要解决这个问题，我们需要做两件事。

首先，每当我们连接到rabbitmq，我们需要一个新的，空的队列。要做到这一点，我们可以创建一个随机名称的队列，或者甚至更好 - 让服务器为我们选择一个随机队列名称。
我们可以通过不将队列参数提供给queue_declare来实现这一点：

```python
result = channel.queue_declare()
```

此时，*result.method.queue*包含一个随机队列名称。例如，它可能看起来像*amq.gen-i94oCE_tj3LyWsy-94KXHg*。

其次，一旦消费者连接关闭，队列应该被删除。这是一个专有标志：

```python
result = channel.queue_declare(exclusive=True)
```

### 绑定

![](https://img.vim-cn.com/41/e211a972dcd6bbca361008baa276318fadde15.png)

我们已经创建了一个fanout交换和一个队列。现在我们需要告诉交换所将消息发送到我们的队列。交换和队列之间的关系称为绑定。

```python
channel.queue_bind(exchange='logs',
                   queue=result.method.queue)
```

从现在起，*logs* 交易所会将消息附加到我们的队列中。

### 把它放在一起

![](https://img.vim-cn.com/72/3a8a707d1c971f75ebbe6d060206628f4f2ab7.png)

发出日志消息的生产者程序与之前的教程没有多大区别。最重要的变化是我们现在想发布消息到我们的*logs*交易所，而不是无名字的消息。发送时我们需要提供一个*routing_key*，但是对于*fanout*交换，它的值将被忽略。这里是*emit_log.py*脚本的代码 ：

```python
#!/usr/bin/env python
import sys
import pika

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='localhost'))
channel = connection.channel()

channel.exchange_declare(exchange='logs',
                         exchange_type='fanout')

message = ' '.join(sys.argv[1:]) or "info: Hello world!"
channel.basic_publish(exchange='logs',
                      routing_key='',
                      body=message)
print(" [x] Sent %r" % message)
connection.close()
```

如你所见，建立连接后，我们宣布交易所。这一步是必要的，因为发布到不存在的交易所是被禁止的。

如果没有队列绑定到交换机上，这些消息将会丢失，但这对我们来说没问题; 如果没有消费者正在收听，我们可以放心地丢弃消息。

*receive_logs.py*的代码：

```python
#!/usr/bin/env python
import pika

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()

channel.exchange_declare(exchange='logs',
                         exchange_type='fanout')

result = channel.queue_declare(exclusive=True)
queue_name = result.method.queue

channel.queue_bind(exchange='logs',
                   queue=queue_name)

print(' [*] Waiting for logs. To exit press CTRL+C')


def callback(ch, method, properties, body):
    print(" [x] %r" % body)


channel.basic_consume(callback,
                      queue=queue_name,
                      no_ack=True)

channel.start_consuming()
```

我们完成了。如果您想将日志保存到文件中，只需打开一个控制台并输入：

> python receive_logs.py > logs_from_rabbit.log

如果你想在屏幕上看到日志，打开一个新的终端并运行：

> python receive_logs.py

当然，

> python emit_log.py

使用*rabbitmqctl list_bindings*，你可以验证代码是否真正创建了绑定和队列。当有两个*receive_logs.py*程序正在运行，你应该看到如下所示：

```
root@921edcb46341:/# rabbitmqctl list_bindings
Listing bindings for vhost /...
	exchange	amq.gen-6YXn7BycIwtI7kFuUrTbaA	queue	amq.gen-6YXn7BycIwtI7kFuUrTbaA	[]
	exchange	amq.gen-JhFL-rbMAoricMu5Dyo-hA	queue	amq.gen-JhFL-rbMAoricMu5Dyo-hA	[]
logs	exchange	amq.gen-6YXn7BycIwtI7kFuUrTbaA	queue	amq.gen-6YXn7BycIwtI7kFuUrTbaA	[]
logs	exchange	amq.gen-JhFL-rbMAoricMu5Dyo-hA	queue	amq.gen-JhFL-rbMAoricMu5Dyo-hA	[]
```

![](https://img.vim-cn.com/1e/33c717feebcfd0893e3aca58eeb05f61aff593.png)
