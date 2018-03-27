## 说明：

你会看到源代码中：

```python
# connection = pika.BlockingConnection(pika.ConnectionParameters(host='172.17.0.2')) # docker container ip address
```

这样一行。

host='172.17.0.2' 这个 ip 地址是我docker rabbitmq容器的ip地址。

如何查到容器的ip:

- 查看当前有哪些容器:

> docker ps

![](https://img.vim-cn.com/c9/10e73a6d4f688e68ce181177fff68983c101ca.jpg)

然后复制容器的ID

> docker inspect 24d5cac36b7f

![](https://img.vim-cn.com/13/811a352ba0d678c1da2952714966ac9cf738fc.jpg)
