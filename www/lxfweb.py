
import asyncio, os, inspect, logging, functools

from urllib import parse

from aiohttp import web

from apis import APIError

def get(path):
    '''
    Define decorator @get('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper
    return decorator

def post(path):
    '''
    Define decorator @post('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator

def get_required_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)

def get_named_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)

def has_named_kw_args(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True

def has_var_kw_arg(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True

def has_request_arg(fn):
    sig = inspect.signature(fn)
    params = sig.parameters
    found = False
    for name, param in params.items():
        if name == 'request':
            found = True
            continue
        if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
            raise ValueError('request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(sig)))
    return found

class RequestHandler(object):

    def __init__(self, app, fn):
        self._app = app
        self._func = fn
        self._has_request_arg = has_request_arg(fn)
        self._has_var_kw_arg = has_var_kw_arg(fn)
        self._has_named_kw_args = has_named_kw_args(fn)
        self._named_kw_args = get_named_kw_args(fn)
        self._required_kw_args = get_required_kw_args(fn)

    @asyncio.coroutine
    def __call__(self, request):
        kw = None
        if self._has_var_kw_arg or self._has_named_kw_args or self._required_kw_args:
            if request.method == 'POST':
                if not request.content_type:
                    return web.HTTPBadRequest('Missing Content-Type.')
                ct = request.content_type.lower()
                if ct.startswith('application/json'):
                    params = yield from request.json()
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest('JSON body must be object.')
                    kw = params
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                    params = yield from request.post()
                    kw = dict(**params)
                else:
                    return web.HTTPBadRequest('Unsupported Content-Type: %s' % request.content_type)
            if request.method == 'GET':
                qs = request.query_string
                if qs:
                    kw = dict()
                    for k, v in parse.parse_qs(qs, True).items():
                        kw[k] = v[0]
        if kw is None:
            kw = dict(**request.match_info)
        else:
            if not self._has_var_kw_arg and self._named_kw_args:
                # remove all unamed kw:
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            # check named arg:
            for k, v in request.match_info.items():
                if k in kw:
                    logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
                kw[k] = v
        if self._has_request_arg:
            kw['request'] = request
        # check required kw:
        if self._required_kw_args:
            for name in self._required_kw_args:
                if not name in kw:
                    return web.HTTPBadRequest('Missing argument: %s' % name)
        logging.info('call with args: %s' % str(kw))
        try:
            r = yield from self._func(**kw)
            return r
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)

def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/', path)
    logging.info('add static %s => %s' % ('/static/', path))

def add_route(app, fn):
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    if path is None or method is None:
        raise ValueError('@get or @post not defined in %s.' % str(fn))
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        fn = asyncio.coroutine(fn)
    logging.info('add route %s %s => %s(%s)' % (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
    app.router.add_route(method, path, RequestHandler(app, fn))

def add_routes(app, module_name):
    n = module_name.rfind('.')
    if n == (-1):
        mod = __import__(module_name, globals(), locals())
    else:
        name = module_name[n+1:]
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
    for attr in dir(mod):
        if attr.startswith('_'):
            continue
        fn = getattr(mod, attr)
        if callable(fn):
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            if method and path:
                add_route(app, fn)


# import asyncio, os, inspect, logging, functools
#
# from urllib import parse
#
# from aiohttp import web
#
# from apis import APIError
#
# import functools
# def Handler_decorator(path,*,method):
#     def decorator(func):
#         @functools.wraps(func)#更正函数签名
#         def wrapper(*args,**kw):
#             return func(*args,**kw)
#         wrapper.__route__ = path #存储路径信息,注意这里属性名叫route
#         wrapper.__method__ = method #存储方法信息
#         return wrapper
#     return decorator
#
# # 这里用偏函数，固定某些参数，返回一个新的函数。
# # 定义了两个装饰器，get用来获取数据，post用来提交数据; GET，POST，PUT，DELETE就对应着对这个资源的查，改，增，删4个操作。
# get = functools.partial(Handler_decorator,method = 'GET')
# post = functools.partial(Handler_decorator,method = 'POST')
#
#
# #运用inspect模块，创建几个函数用以获取URL处理函数与request参数之间的关系
# def get_required_kw_args(fn): #收集没有默认值的命名关键字参数
#     args = []
#     params = inspect.signature(fn).parameters #inspect模块是用来分析模块，函数
#     for name, param in params.items():
#         if str(param.kind) == 'KEYWORD_ONLY' and param.default == inspect.Parameter.empty:
#             args.append(name)
#     return tuple(args)
#
# def get_named_kw_args(fn):  #获取命名关键字参数
#     args = []
#     params = inspect.signature(fn).parameters
#     for name,param in params.items():
#         if str(param.kind) == 'KEYWORD_ONLY':
#             args.append(name)
#     return tuple(args)
#
# def has_named_kw_arg(fn): #判断有没有命名关键字参数
#     params = inspect.signature(fn).parameters
#     for name,param in params.items():
#         if str(param.kind) == 'KEYWORD_ONLY':
#             return True
#
# def has_var_kw_arg(fn): #判断有没有关键字参数
#     params = inspect.signature(fn).parameters
#     for name,param in params.items():
#         if str(param.kind) == 'VAR_KEYWORD':
#             return True
#
# def has_request_arg(fn): #判断是否含有名叫'request'参数，且该参数是否为最后一个参数
#     params = inspect.signature(fn).parameters
#     sig = inspect.signature(fn)
#     found = False
#     for name,param in params.items():
#         if name == 'request':
#             found = True
#             continue #跳出当前循环，进入下一个循环
#         if found and (str(param.kind) != 'VAR_POSITIONAL' and str(param.kind) != 'KEYWORD_ONLY' and str(param.kind != 'VAR_KEYWORD')):
#             raise ValueError('request parameter must be the last named parameter in function: %s%s'%(fn.__name__,str(sig)))
#     return found
#
# # RequestHandler目的就是从URL函数中分析其需要接收的参数，从request中获取必要的参数，调用URL函数，然后把结果转换为web.Response对象
# class RequestHandler(object):
#
#     def __init__(self,app,fn):#接受app，fn参数
#         self._app = app
#         self._fn = fn
#         self._required_kw_args = get_required_kw_args(fn)
#         self._named_kw_args = get_named_kw_args(fn)
#         self._has_named_kw_arg = has_named_kw_arg(fn)
#         self._has_var_kw_arg = has_var_kw_arg(fn)
#         self._has_request_arg = has_request_arg(fn)
#
#     @asyncio.coroutine   #__call__这里要构造协程
#     def __call__(self,request):  #定义__call__,可以将其实例视为函数
#         kw = None
#         if self._has_named_kw_arg or self._has_var_kw_arg:
#             if request.method == 'POST': #判断客户端发来的方法是否为POST
#                 if not request.content_type: #查询有没提交数据的格式（EncType）
#                     return web.HTTPBadRequest(text='Missing Content_Type.')#这里被廖大坑了，要有text
#                 ct = request.content_type.lower() #小写
#                 if ct.startswith('application/json'): #startswith
#                     params = yield from request.json() #Read request body decoded as json.
#                     if not isinstance(params,dict):
#                         return web.HTTPBadRequest(text='JSON body must be object.')
#                     kw = params
#                 elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
#                     params = yield from request.post() # reads POST parameters from request body.If method is not POST, PUT, PATCH, TRACE or DELETE or content_type is not empty or application/x-www-form-urlencoded or multipart/form-data returns empty multidict.
#                     kw = dict(**params)
#                 else:
#                     return web.HTTPBadRequest(text='Unsupported Content_Tpye: %s'%(request.content_type))
#             if request.method == 'GET':
#                 qs = request.query_string #The query string in the URL
#                 if qs:
#                     kw = dict()
#                     for k,v in parse.parse_qs(qs,True).items(): #Parse a query string given as a string argument.Data are returned as a dictionary. The dictionary keys are the unique query variable names and the values are lists of values for each name.
#                         kw[k] = v[0]
#         if kw is None:
#             kw = dict(**request.match_info)
#         else:
#             if not self._has_var_kw_arg and self._named_kw_args: #当函数参数没有关键字参数时，移去request除命名关键字参数所有的参数信息
#                 copy = dict()
#                 for name in self._named_kw_args:
#                     if name in kw:
#                         copy[name] = kw[name]
#                 kw = copy
#             for k,v in request.match_info.items(): #检查命名关键参数
#                 if k in kw:
#                     logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
#                 kw[k] = v
#         if self._has_request_arg:
#             kw['request'] = request
#         if self._required_kw_args: #假如命名关键字参数(没有附加默认值)，request没有提供相应的数值，报错
#             for name in self._required_kw_args:
#                 if name not in kw:
#                     return web.HTTPBadRequest(text='Missing argument: %s'%(name))
#         logging.info('call with args: %s' % str(kw))
#
#         try:
#             r = yield from self._fn(**kw)
#             return r
#         except APIError as e: #APIError另外创建
#             return dict(error=e.error, data=e.data, message=e.message)
#
# # 用来处理URL处理函数，主要用来验证函数是否包含URL的响应方法和路径信息，以及将函数变成协程
# def add_route(app,fn):
#     method = getattr(fn,'__method__',None)
#     path = getattr(fn,'__route__',None)
#     if method is None or path is None:
#         return ValueError('@get or @post not defined in %s.'%str(fn))
#     if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn): #判断是否为协程且生成器,不是使用isinstance
#         fn = asyncio.coroutine(fn)
#     logging.info('add route %s %s => %s(%s)'%(method,path,fn.__name__,','.join(inspect.signature(fn).parameters.keys())))
#     app.router.add_route(method,path,RequestHandler(app,fn)) #RequestHandler的参数有两个
#
#
# #直接导入文件，批量注册一个URL处理函数  只需向这个函数提供要批量注册函数的文件路径，新编写的函数就会筛选，注册文件内所有符合注册条件的函数。
# def add_routes(app,module_name):
#     n = module_name.rfind('.')
#     if n == -1:
#         mod = __import__(module_name,globals(),locals())
#     else:
#         name = module_name[n+1:]
#         mod = getattr(__import__(module_name[:n],globals(),locals(),[name],0),name)#第一个参数为文件路径参数，不能掺夹函数名，类名
#     for attr in dir(mod):
#         if attr.startswith('_'):
#             continue
#         fn = getattr(mod,attr)
#         if callable(fn):
#             method = getattr(fn,'__method__',None)
#             path = getattr(fn,'__route__',None)
#             if path and method: #这里要查询path以及method是否存在而不是等待add_route函数查询，因为那里错误就要报错了
#                 add_route(app,fn)
#
# # 添加静态文件的路径
# def add_static(app):
#     path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
#     app.router.add_static('/static/', path)
#     logging.info('add static %s => %s' % ('/static/', path))
