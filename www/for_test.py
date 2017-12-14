import orm
from models import User, Blog, Comment
import sys, asyncio

def test(loop):
    yield from orm.create_pool(loop=loop, user='root', password='abc230002', db='awesome')
    # 在尝试换掉这些数据，不然会报错
    u = User(name='Test3', email='test@example2.com', passwd='1234567890', image='about:blank')
    yield from u.save()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.wait([test(loop)]))
    loop.close()
    if loop.is_closed():
        sys.exit(0)
