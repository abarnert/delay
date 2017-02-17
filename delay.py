#!/usr/bin/env python3

import functools
import inspect

_delayedtypes = {}
_annotated = object()

def delay(func, typ=_annotated):
    if typ is _annotated:
        try:
            typ = func.__annotations__['return']
        except KeyError:
            raise TypeError('delay can only be called on annotated functions')
    # TODO: string types?
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
            # TODO: Is this the right list? I'm sure __getattribute__
            # needs special handling, although I don't think __getattr__
            # and friends do. And __init__, for classes that re-init
            # after construction?
            if (name not in ('__new__', '__init__') and
                inspect.isroutine(method)):
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

if __name__ == '__main__':
    import typing
    @delay
    def thunk() -> typing.List[int]:
        print("Help, I'm being evaluated!")
        return [1, 2, 3]
    h = thunk
    print('Assigned it to a variable')
    def donothing(x):
        pass
    donothing(thunk)
    print('Passed it to a function')
    if h:
        pass
    print('Did a bool test on it')
    print(h)

    class SillySeq:
        def __getitem__(self, idx):
            return idx
    @delay
    def silly() -> SillySeq:
        return SillySeq()
    i = iter(silly)
    print(next(i))
    
    
    d = delay(lambda: silly, typ=SillySeq)
    i = iter(d)
    print(next(i))
