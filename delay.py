#!/usr/bin/env python3

import functools
import inspect

_delayedtypes = {}

def delay(func):
    try:
        typ = func.__annotations__['return']
    except KeyError:
        raise TypeError('delay can only be called on annotated functions')
    if typ not in _delayedtypes:
        # TODO: Is dir good enough for a wrapped type? Obviously
        #       won't work for __getattr__, but then nothing will
        #       except explicitly handling all special method names
        methods = [name for name in dir(typ)
                   if inspect.isroutine(getattr(typ, name))]
        methdict = {}
        def __new__(cls, func):
            self = object.__new__(cls)
            object.__setattr__(self, '__func__', func)
            return self
        methdict['__new__'] = __new__
        for name in dir(typ):
            method = getattr(typ, name)
            if name != '__new__' and inspect.isroutine(method):
                def make_wrapper(name, method):
                    @functools.wraps(method)
                    def wrapper(self, *args, **kw):
                        #print(name, method, type(self), args, kw)
                        try:
                            value = object.__getattribute__(self, '__value__')
                        except AttributeError:
                            func = object.__getattribute__(self, '__func__')
                            #print('evaluating', func)
                            value = func()
                            object.__setattr__(self, '__value__', value)
                        return method(value, *args, **kw)
                    return wrapper
                methdict[name] = make_wrapper(name, method)
        # TODO: Add __module__ and/or __qualname__ to methdict?
        name = 'Delayed({})'.format(typ.__qualname__)
        # TODO: Can we safely call a nonstandard metaclass?
        _delayedtypes[typ] = type(typ)(name, (object,), methdict)
    return _delayedtypes[typ](func)

def f() -> int: return 2
def g() -> int: return 3

d = delay(f)
print(d + 2)
d2 = delay(g)
print(2 + d2)

@delay
def h() -> int: return 4
print(h)
