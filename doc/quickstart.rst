Quickstart
==========

Morepath is a micro-framework, and this makes it small and easy to
learn. This quickstart guide should help you get started. We assume
you've already installed Morepath; if not, see the :ref:`installation`
section.

Hello world
-----------

Let's look at a minimal "Hello world!" application in Morepath::

  import morepath

  app = morepath.App()

  @app.root()
  class Root(object):
      pass

  @app.view(model=Root)
  def hello_world(request, model):
      return "Hello world!"

  if __name__ == '__main__':
      config = morepath.setup()
      config.scan()
      config.commit()
      app.run()

You can save this as ``hello.py`` and then run it with Python:

.. code-block:: sh

  $ python hello.py
  * Running on http://127.0.0.1:5000/

.. sidebar:: Making the server externally accessible

  The default configuration of ``run()`` uses the ``127.0.0.1`` hostname.
  This means you can access the web server from your own computer, but
  not from anywhere else. During development this is often the best way
  to go about things.

  But for deployment you do want to make your server accessible from
  the outside world. This can be done by passing an explicit ``host``
  argument of ``0.0.0.0`` to the ``run()`` method::

    app.run(host='0.0.0.0')

  Note that for more sophisticated deployment scenarios you wouldn't
  use ``run()`` at all, but instead use an external WSGI server such
  as waitress_, `Apache mod_wsgi`_ or `nginx mod_wsgi`_.

  .. _waitress: http://pylons.readthedocs.org/projects/waitress/en/latest/

  .. _`Apache mod_wsgi`: https://modwsgi.readthedocs.org/en/latest/

  .. _`nginx mod_wsgi`: http://wiki.nginx.org/NgxWSGIModule

If you now go with a web browser to the URL given, you should see
"Hello world!"  as expected. When you want to stop the server, just
press control-C.

This application is a bit bigger than you might be used to in other
web micro-frameworks. That's for a reason: Morepath is not geared to
create the most succinct "Hello world!" application but to be
effective for building slightly larger applications, all the way up to
huge ones.

Let's go through the hello world app step by step to gain a better
understanding.

Code Walkthrough
----------------

1. We import ``morepath``.

2. We create an instance of :class:`morepath.App`. This will be a WSGI
   application that we can run. It will also contain our application's
   configuration: what models and views are available.

3. We then set up a ``Root`` class. Morepath is model-driven and in
   order to create any views, we first need at least one model, in
   this case the empty ``Root`` class.

   The simplest way we can expose a model to the web is as the root of
   the website (``/``). You do this with the
   :meth:`morepath.AppBase.root` decorator.

4. Now we can create the "Hello world" view. It's just a function that
   takes ``request`` and ``model`` as arguments (we don't need to use
   either in this case), and returns the string ``"Hello world!"``.

   We then need to hook up this view with the
   :meth:`morepath.AppBase.view` decorator.  We say it's associated
   with the ``Root`` model. Since we supply no explicit ``name`` to
   the decorator, we will be the default view for the ``Root`` model
   on ``/``.

5. The ``if __name__ == '__main__'`` section is a way in Python to
   make the code only run if the ``hello.py`` module is started
   directly with Python as discussed above. In a real-world
   application you instead use a setuptools entry point so that a
   startup script for your application is created automatically.

6. func:`morepath.setup` sets up Morepath's default behavior, and
   returns a Morepath config object. If your app is in a Python
   package and you've set up the right ``install_requires`` in
   ``setup.py``, consider using :func:`morepath.autosetup` to be done
   in one step.

7. We then ``scan()`` this module (or package) for configuration
   decorators (such as :meth:`morepath.AppBase.root` and
   :meth:`morepath.AppBase.view`) and cause the registration to be
   registered using :meth:`morepath.Config.commit`.

   This step ensures your configuration (model routes, views, etc) is
   loaded exactly once in a way that's reusable and extensible.

8. We then run the ``WSGI`` app using the default web server. Since
   ``app`` is a WSGI app you can also plug it into any other WSGI
   server.

Routing
-------

Morepath uses a special routing technique that is different from many
other routing frameworks you may be familiar with. Morepath does not
route to views, but routes to models instead.

.. sidebar:: Why route to models?

  Why does Morepath route to models? It allows for some nice
  features. The most concrete feature is automatic hyperlink
  generation - we'll go into more detail about this later.

  A more abstract feature is that Morepath through model-driven
  application allows for greater code reuse: this is the basis for
  Morepath's super-powers. We'll show a few of these special things
  you can do with Morepath later.

  Finally Morepath's model-oriented nature makes it a more natural fit
  for REST_ applications. This is useful when you need to create a web
  service or the foundation to a rich client-side application.

  .. _REST: https://en.wikipedia.org/wiki/Representational_state_transfer

Models
~~~~~~

A model is any Python object that represents the content of your
application: say a document, or a user, an address, and so on. A model
may be a plain in-memory Python object or be backed by a database
using an ORM such as SQLAlchemy_, or some NoSQL database such as the
ZODB_. This is entirely up to you; Morepath does not put special
requirements on models.

.. _SQLAlchemy: http://www.sqlalchemy.org/

.. _ZODB: http://www.zodb.org/en/latest/

Above we've exposed a ``Root`` model to the root route ``/``, which is
rather boring. To make things more interesting, let's imagine we have
an application to manage users. Here's our ``User`` class::

  class User(object):
       def __init__(self, username, fullname, email):
           self.username = username
           self.fullname = fullname
           self.email = email

We also create a simple users database::

  users = {}
  def add_user(user):
       users[user.username] = user

  faassen = User('faassen', 'Martijn Faassen', 'faassen@startifact.com')
  bob = User('bob', 'Bob Bobsled', 'bob@example.com')
  add_user(faassen)
  add_user(bob)

Publishing models
~~~~~~~~~~~~~~~~~

We want our application to have URLs that look like this::

  /user/faassen

  /user/bob

Here's the code to expose our users database to such a URL::

  @app.model(model=User, path='/user/{username}',
             variables=lambda user: { 'username': user.username})
  def get_user(username):
      return users.get(username)

The ``get_user`` function gets a user model from the users database by
using the dictionary ``get`` method. If the user doesn't exist, it
will return ``None``. We could've fitted a SQLAlchemy query in here
instead.

Now let's look at the decorator. The ``model`` argument has the class
of the model that we're putting on the web. The ``path`` argument has
the URL path under which it should appear.

The path can have variables in it which are between curly braces
(``{`` and ``}``). These variables become arguments to the function
being decorated. If we have variables in our path, we also need to
supply ``variables``. This is a function that given a model can
construct the variables that go into the path. In this case, we know
we need the username and we can get it from the ``user``
object. ``variables`` is important for link generation, as we'll see
later.

What if the user doesn't exist? We want the end-user to see a 404
error.  Morepath does this automatically for you when you return
``None`` for a model, which is what ``get_user`` does when the model
cannot be found.

Now we've published the model to the web but we can't view it yet.

.. sidebar:: int converter

  A common use case is for path variables to be a database id. These
  are often integers only. If a non-integer is seen in the path we
  know it doesn't match. You can specify a path variable contains an
  integer using the integer converter (``:int``). For instance::

    posts/{post_id:int}

Views
~~~~~

In order to actually see a web page for a user model, we need to
create a view for it::

  @app.view(model=User)
  def user_info(request, model):
      return "User's full name is: %s" % model.fullname

The view is a function decorated by :meth:`morepath.AppBase.view` (or
related decorators such as :meth:`morepath.AppBase.json` and
:meth:`morepath.AppBase.html`) that gets two arguments: ``request``
which is a :class:`morepath.Request` object (a subclass of
:class:`werkzeug.wrappers.BaseRequest`), and ``model`` which is the
model that this view is working for, so in this case an instance of
``User``.

Now the URLs listed above such as ``/user/faassen`` will work.

What if we want to provide an alternative view for the user, such as
an ``edit`` view which allows us to edit it? We need to give it a
name::

  @app.view(model=User, name='edit')
  def edit_user(request, model):
      return "An editing UI goes here"

Now we have functionality on URLs like ``/user/faassen/edit`` and
``/user/bob/edit``.

Linking to models
~~~~~~~~~~~~~~~~~

Morepath is great at creating links to models: it can do it for you
automatically. Previously we've defined an instance of ``User`` called
``bob``. What now if we want to link to the default view of ``bob``?
We simply do this::

  request.link(bob)

which will generate the path ``/user/bob`` for us.

What if we want to see Bob's edit view? We do this::

  request.link(bob, 'edit')

And we'll get ``/user/bob/edit``.

Using :meth:`morepath.Request.link`` everywhere for link generation is
easy. You only need models and remember which view names are
available, that's it. If you ever have to change the path of your
model, you won't need to adjust any linking code.

.. sidebar:: Link generation compared

  If you're familiar with routing frameworks where links are generated
  to views (such as Flask or Django) link generation is more
  involved. You need to give each route a name, and then refer back to
  this route name when you want to generate a link. You also need to
  supply the variables that go into the route. With Morepath, you
  don't need a route name, and you only need to explain once how to
  create the variables for a route, with the ``variables`` argument to
  ``@app.model``.

JSON and HTML views
~~~~~~~~~~~~~~~~~~~

``@app.view`` is rather bare-bones. You usually know more about what
you want to return than that. If you want to return JSON, you can use
the shortcut ``@app.json`` instead to declare your view::

  @app.json(model=User, name='info')
  def user_json_info(request, model):
      return {'username': model.username,
              'fullname': model.fullname,
              'email': model.email}

This automatically serializes what is returned from the function JSON,
and sets the content-type header to ``application/json``.

If we want to return HTML, we can use ``@app.html``::

  @app.html(model=User)
  def user_info(request, model):
      return "<p>User's full name is: %s</p>" % model.fullname

This automatically sets the content type to ``text/html``. It doesn't
do any HTML escaping though, so the use of ``%`` above is unsafe! We
recommend the use of a HTML template language in that case.

Request object
--------------

The first argument for a view function is the request object. We'll
give a quick overview of what's possible here, but consult the
Werkzeug API documentation for more information.

* ``request.args`` contains any URL parameters (``?key=value``). See
  :attr:`werkzeug.wrappers.BaseRequest.args`.

* ``request.form`` contains any HTTP form data that was submitted. See
  :attr:`werkzeug.wrappers.BaseRequest.form`.

* ``request.method`` gets the HTTP method (``GET``, ``POST``, etc). See
  :attr:`werkzeug.wrappers.BaseRequest.method`.

* Uploaded files made available in ``request.files``. See
  :attr:`werkzeug.wrappers.BaseRequest.files`.

  The keys are the form fields with which they were uploaded. The
  values are Python ``file`` style objects, but with a ``save()``
  method added that allows you to store that file on the
  filesystem. There is also a ``filename`` attribute that gives the
  filename of the file that was uploaded; if you want to use this to
  store the file, use :func:`werkzeug.utils.secure_filename` to secure
  it first. Make sure your HTML form has
  ``enctype="multipart/form-data"`` set to make file uploads work.

* ``request.cookies`` contains the cookies. See
  :attr:`werkzeug.wrappers.BaseRequest.cookies`. ``response.set_cookie``
  can be used to set cookies. See
  :meth:`werkzeug.wrappers.BaseResponse.set_cookie`.

Redirects
---------

To redirect to another URL, use :func:`morepath.redirect`. For example::

  @app.view(model=User, name='extra')
  def redirecting(request, model):
      return morepath.redirect(request.link(model, 'other'))

HTTP Errors
-----------

To trigger an HTTP error response you can raise various Werkzeug HTTP
exceptions (:mod:`werkzeug.exceptions`). For instance::

  from werkzeug.exceptions import NotAcceptable

  @app.view(model=User, name='extra')
  def erroring(request, model):
      raise NotAcceptable()
