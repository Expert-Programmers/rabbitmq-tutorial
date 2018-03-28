# 路由

## 本章节教程重点介绍的内容

在之前的教程中，我们构建了一个简单的日志系统 我们能够将日志消息广播给许多接收者。

在本教程中，我们将添加一个功能 - 我们将只能订阅一部分消息。例如，我们只能将重要的错误消息引导到日志文件（以节省磁盘空间），同时仍然能够在控制台上打印所有日志消息。

### 绑定

在前面的例子中，我们已经创建了绑定。您可能会回想一下代码：

```python
channel.queue_bind(exchange=EXCHANGE_NAME,
                   queue=queue_name)
```

绑定是交换和队列之间的关系。这可以简单地理解为： the queue is interested in messages from this exchange.

绑定可以使用额外的*routing_key*参数。为了避免与*basic_publish*参数混淆，我们将其称为*绑定键*。这就是我们如何使用一个键创建一个绑定：

```python
channel.queue_bind(exchange=exchange_name,
                   queue=queue_name,
                   routing_key='black')
```

绑定键的含义取决于交换类型。我们之前使用的 *fanout* 交换简单地忽略了它的价值。

### 直接交换

我们之前教程的日志记录系统将所有消息广播给所有消费者。我们希望将其扩展为允许根据其进行严格的过滤消息。
例如，我们可能希望将严重错误的日志消息写入磁盘，而不会写入警告或信息日志消息。

我们正在使用*fanout*交换，这不会给我们太多的灵活性 - 它只能无意识地播放。

我们将使用*direct*交换。*direct*交换背后的路由算法很简单 - 消息进入队列，其*绑定密钥*与消息的*路由密钥*完全匹配。

为了说明这一点，请考虑以下设置：

![](https://img.vim-cn.com/93/6cf5ed800ccd2fd9b9ab3989b606fd37d9799b.png)

在这个设置中，我们可以看到有两个队列绑定的直接交换机*X*. 第一个队列用绑定键*orange*绑定，第二个队列有两个绑定，一个绑定键为*black*，另一个为*green*。

在这种设置中，使用路由键*orange*发布到交换机的消息 将被路由到队列*Q1*。带有*black*或*gree*路由键的消息将进入*Q2*。所有其他消息将被丢弃。

### 多个绑定

![](https://img.vim-cn.com/ac/209b52a7e280b8b46230d2d3f8e636100c6506.png)

使用相同的绑定密钥绑定多个队列是完全合法的。在我们的例子中，我们可以使用绑定键*black*添加*X*和*Q1*之间的绑定。
在这种情况下，*direct*交换就像*fanout*一样，并将消息广播到所有匹配的队列。带有路由键*black*的消息将传送到*Q1*和*Q2*。

### 发出日志

我们将使用这个模型用于我们的日志系统。取而代之的*fanout*，我们将消息发送到*direct*交换。我们将提供严格的日志作为路由键(*routing key*)。
这样接收脚本将能够选择想要接收的消息。我们先关注发出日志的实现。

像往常一样，我们需要首先创建一个交换：

```python
channel.exchange_declare(exchange='direct_logs',
                         exchange_type='direct')
```

我们准备发送一条消息：

```python
channel.basic_publish(exchange='direct_logs',
                      routing_key='',
                      body=message)
```

为了简化事情，我们将假设“severity”可以是'info'，'warning'，'error'之一。

### 订阅

接收邮件的方式与上一个教程中的一样，只有一个例外 - 我们将为每个我们感兴趣的严重程度创建一个新绑定。

```python
result = channel.queue_declare(exclusive=True)
queue_name = result.method.queue

for severity in severities:
    channel.queue_bind(exchange='direct_logs',
                       queue=queue_name,
                       routing_key=severity)
```

### 把它放在一起

![](https://img.vim-cn.com/98/61354f4fbfa294918aa23d917d59a47a2dcbb4.png)

*emit_log_direct.py*的代码：
```python
#!/usr/bin/env python
import sys
import pika

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))

channel = connection.channel()

channel.exchange_declare(exchange='direct_logs',
                         exchange_type='direct')

severity = sys.args[1:] if len(sys.argv) > 2 else 'info'
message = ' '.join(sys.argv[2:]) or 'Hello World!'
channel.basic_publish(exchange='direct_logs',
                      routing_key=severity, body=message)
print(" [x] Sent %r:%r" % (severity, message))
connection.close()
```

*receive_logs_direct.py*的代码：

```python
#!/usr/bin/env python
import sys
import pika

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()

channel.exchange_declare(exchange='direct_logs',
                         exchange_type='direct')

result = channel.queue_declare(exclusive=True)
queue_name = result.method.queue

severities = sys.argv[1:]
if not severities:
    sys.stderr.write("Usage: %s [info] [warning] [error]\n" % sys.argv[0])
    sys.exit(1)

for severity in severities:
    channel.queue_bind(exchange='direct_logs',
                       queue=queue_name,
                       routing_key=severity)

print(' [*] Waiting for logs. To exit press CTRL+C')


def callback(cb, method, properities, body):
    print(" [x] %r:%r" % (method.routing_key, body))


channel.basic_consume(callback,
                      queue=queue_name,
                      no_ack=True)

channel.start_consuming()
```

如果只想保存'*warning*'和'*error*'（而不是'*info*'）将消息记录到文件中，只需打开一个控制台并输入：

> python receive_logs_direct.py warning error > logs_from_rabbit.log

如果您希望在屏幕上看到所有日志消息，请打开一个新终端并执行以下操作：

> python receive_logs_direct.py info warning error

例如，要输出*error*日志消息，只需输入：

> python emit_log_direct.py error "Run. Run. Or it will explode."
