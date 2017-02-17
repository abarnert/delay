# delay
Create "thunks" as painlessly as possible.

There is a limit to how painless that is, at least as of Python 3.6, 
but this is a nice way to explore and play around with that limit.

A delayed thunk is a lazy value, which is evaluated the first time you
try to access any of its attributes (including things like `__repr__`).

To create one, you have to have a nullary function, with a return
annotation, that produces the value. Like this:

    def zero() -> int:
        return 0
    thunk = delay(zero)

If it's a one-shot function, you can use decorator syntax, but it 
doesn't buy you that much:

    @delay
    def thunk() -> int:
        return 0

Notice that you can't use lambdas, because lambdas can't to be annotated.
However, you can pass the return type explicitly as an extra argument.
(This doesn't work with decorator syntax, but then you can't decorate
lambdas, and if you're decorating a `def` you might as well annotate it
instead.)

    thunk = delay(lambda: 2, int)

Now you can pass your thunk around, assign it to variables, etc., without
the function being called. But as soon as you try to use it as a value in
any way, it will be.

Of course a realistic example will be something slow or dangerous to
evaluate, or at the very least visible. We can do that pretty easily:

    @delay
    def thunk() -> int:
        print("Help, I'm being evaluated!")
        return 0
    h = thunk
    print('Assigned it to a variable')
    def donothing(x):
        pass
    donothing(thunk)
    print('Passed it to a function')
    if h:
        pass
    print('Did a bool test on it')

Most things should just work as you'd expect, unless you start doing
things like changing your type after creation in the wrapped types.

What if you delay a thunk? You can't, but you can delay a function
that returns a thunk, and you can even specify the "deep" return
type, in which case the inner thunk acts like it isn't there (except
for wasting a bit of memory and CPU):

    thunk2 = delay(lambda: thunk, int)
    print(thunk2) # 0
    
==Syntax Ideas==

What we really want to be able to write is something like this:

    thunk = <: expensive1() + expensive2() :>
    
instead of this:

    thunk = delay(lambda: expensive1() + expensive2(), str)

I mean, not something as ugly as `<:`, but you get the idea. 
Really, this is just the "syntax-light lambda" issue, except for
the whole return type thing. And you can already use MacroPy if
you really care about the syntax, but it won't help for the
return type.

So, what about the return type thing? Python's never going to
infer the type for us. A static checker like MyPy might, and you 
could of course write a build script that runs MyPy to infer the 
types and then fills them in, but at that point you could also 
have the build script transform your pet light-lambda syntax 
as well.

Really, what we want is a way to get rid of needing the return
type in the first place. And the problem there isn't anything to 
do with Python syntax, but with building perfect proxyies.

==Implementation==

So, why do we need annotations (or explicit types)?

Because we need to know the type of the value we're delaying if we
want to act like a proxy for that value. We don't have the value
itself (the whole point is to avoid evaluating it yet), so the only
way to get the type is for someone else to tell us.

But why do we need to know the type? Because you can't build a
perfect proxy in Python without knowing the type you're proxying
for. Now, you may say "I don't care about perfect, just good 
enough", but we're talking about things like an `int` proxy not 
working in arithmetic expressions, or a `list` proxy not working 
in a `for` loop, which is generally not good enough.

Why can't we build a perfect proxy without knowing the type? Well,
a few things (like making `dir` and `help` work) can't be faked
with the usual dynamic lookup via `__getattr__`, but that may be
livable. The bigger problem is that the special methods used to 
make our object work in arithmetic expressions or `for` loops are 
looked up on the class rather than the instance, and may even be 
looked up directly in the class's dictionary rather than
dynamically. There's just no way to hook things so that
`thunk + 2` will work unless `thunk`'s type has an `__add__`
method defined statically on the type.

Couldn't we just define passthrough methods for every special
method in the language, so every thunk implements `__add__` and
`__getitem__` and so on, just raising `AttributeError` if the
delayed value itself doesn't? We'd have to simulate special 
method lookup on the delayed value, which is technically not
even possible (the language doesn't define which methods get
which kind of special lookup, and there's no way to check at
runtime short of keeping a list of every known implementation
and version), but if we're just looking for "good enough", 
that's fine. Also, in many cases you'd get the wrong error,
such as calling `list(x)` on a delayed `int` giving you an
`AttributeError` instead of a `TypeError`, but again, that
might be acceptable. The big problem is that you break all the
fallback mechanisms. The simplest one to demonstrate (although
nowhere near the most important) is iteration fallback:

    class SillySeq:
        def __getitem__(self, idx):
            if idx > 3: raise IndexError
            return idx
                
    class Proxy:
        def __init__(self, thing):
            self.thing = thing
        def __getitem__(self, *args, **kw):
            return self.thing.__getitem__(*args, **kw)
        def __iter__(self, *args, **kw):
            return self.thing.__iter__(*args, **kw)
    
    seq = SillySeq()
    prox = Proxy(seq)
    print(seq[0]) # 0
    print(prox[0]) # 0
    print(list(seq)) # [0, 1, 2]
    print(list(prox)) # AttributeError

Also, a generic proxy has to decide what to do about 
`__getattr__` and friends. If you don't implement it, you can't
handle types with normal attributes--but if you do, you can't 
handle types with dynamic attributes. But a per-class generated
proxy handles that automatically. If the wrapped class has
`__getattr__` for dynamic attributes, we build a wrapper that
calls it; if not, we don't. Even if they implement the
`__getattribute__` method (well, we need a bit of special 
handling for that, but it's not hard, I'm just too lazy to
write it when YAGNI).

Anyway, if there were a way to tell Python "don't do special
method lookup on this class"... Well, as-is that's a non-
starter because it runs into the metaclass confusion problem
described in the docs, but move it up to the metaclass, so
"don't do special method lookup on instances of this 
metaclass", then it gets into the realm of consenting adults;
nobody's going to use that feature who doesn't understand
what they're doing and how it works. We'd really only be
losing an optimization at that point. And if you're passing
around thunks with implicit lazy evaluation, I don't think
you care about that particular optimization for this part
of your code.
