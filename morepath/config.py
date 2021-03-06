from copy import copy
import venusian
from .error import ConflictError
from .framehack import caller_package


class Configurable(object):
    """Object to which configuration actions apply.

    Actions can be added to a configurable. The configurable is then
    prepared. This checks for any conflicts between configurations and
    the configurable is expanded with any configurations from its
    extends list. Then the configurable can be performed, meaning all
    its actions will be performed (to it).
    """
    def __init__(self, extends=None):
        """
        :param extends:
          the configurables that this configurable extends. Optional.
        :type extends: list of configurables, single configurable.
        """
        if extends is None:
            extends = []
        if not isinstance(extends, list):
            extends = [extends]
        self.extends = extends
        self.clear()

    def clear(self):
        """Clear any previously registered actions.

        This is normally not invoked directly, instead is called
        indirectly by :meth:`Config.commit`.
        """
        self._actions = []
        self._action_map = None

    def action(self, action, obj):
        """Register an action with configurable.

        This is normally not invoked directly, instead is called
        indirectly by :meth:`Config.commit`.

        :param action: The action to register with the configurable.
        :param obj: The object that this action will be performed on.
        """
        self._actions.append((action, obj))

    def prepare(self):
        """Prepare configurable.

        This is normally not invoked directly, instead is called
        indirectly by :meth:`Config.commit`.

        Detect any conflicts between actions within this
        configurable. Merges in configuration of those configurables
        that this configurable extends.

        Prepare must be called before perform is called.
        """
        # check for conflicts and fill action map
        discriminators = {}
        self._action_map = action_map = {}
        for action, obj in self._actions:
            id = action.identifier()
            discs = [id]
            discs.extend(action.discriminators())
            for disc in discs:
                other_action = discriminators.get(disc)
                if other_action is not None:
                    raise ConflictError([action, other_action])
                discriminators[disc] = action
            action_map[id] = action, obj
        # inherit from extends
        for extend in self.extends:
            self.combine(extend)

    def combine(self, configurable):
        """Combine actions in another prepared configurable with this one.

        Those configuration actions that would conflict are taken to
        have precedence over those in the configurable that is being
        combined with this one. This allows the extending configurable
        to override configuration in extended configurables.

        :param configurable: the configurable to combine with this one.
        """
        to_combine = configurable._action_map.copy()
        to_combine.update(self._action_map)
        self._action_map = to_combine

    def perform(self):
        """Perform actions in this configurable.

        Prepare must be called before calling this.
        """
        values = self._action_map.values()
        values.sort(key=lambda (action, obj): (-action.priority, action.order))
        for action, obj in values:
            action.perform(self, obj)


class Action(object):
    """A configuration action.

    A configuration action is performed on an object. Actions can
    conflict with each other based on their identifier and
    discriminators. Actions can override each other based on their
    identifier.

    Can be subclassed to implement concrete configuration actions.

    Classes (or action instances) can have a ``priority`` attribute.
    Actions with higher priority will be performed first for a
    configurable. This makes it possible to design actions that depend
    on other actions having been performed.
    """
    priority = 0

    def __init__(self, configurable):
        """
        :param configurable: :class:`morepath.config.Configurable` object
          for which this action was configured.
        """
        self.configurable = configurable
        self.order = None

    def identifier(self):
        """Returns an immutable that uniquely identifies this config.

        Used for overrides and conflict detection.
        """
        raise NotImplementedError()

    def discriminators(self):
        """Returns a list of immutables to detect conflicts.

        Used for additional configuration conflict detection.
        """
        return []

    def clone(self, **kw):
        """Make a clone of this action.

        Keyword parameters can be used to override attributes in clone.

        Used during preparation to create new fully prepared actions.
        """
        action = copy(self)
        for key, value in kw.items():
            setattr(action, key, value)
        return action

    def prepare(self, obj):
        """Prepare action for configuration.

        :param obj: The object that the action should be performed on.

        Returns an iterable of prepared action, obj tuples.
        """
        return [(self, obj)]

    def perform(self, configurable, obj):
        """Register whatever is being configured with configurable.

        :param configurable: the :class:`morepath.config.Configurable`
          being configured.
        :param obj: the object that the action should be performed on.
        """
        raise NotImplementedError()


class Directive(Action):
    """An :class:`Action` that can be used as a decorator.

    Extends :class:`morepath.config.Action`.

    Base class for concrete Morepath directives such as ``@app.model()``,
    ``@app.view()``, etc.

    Can be used as a Python decorator.

    Can also be used as a context manager for a Python ``with``
    statement. This can be used to provide defaults for the directives
    used within the ``with`` statements context.

    When used as a decorator will track where in the source code
    the directive was used for the purposes of error reporting.
    """

    def __init__(self, configurable):
        """
        :param configurable: :class:`morepath.config.Configurable` object
          for which this action was configured.
        """
        super(Directive, self).__init__(configurable)
        self.attach_info = None

    def codeinfo(self):
        """Info about where in the source code the directive was invoked.
        """
        if self.attach_info is None:
            return None
        return self.attach_info.codeinfo

    def __enter__(self):
        return DirectiveAbbreviation(self)

    def __exit__(self, type, value, tb):
        if tb is not None:
            return False

    def __call__(self, wrapped):
        """Call with function to decorate.
        """
        def callback(scanner, name, obj):
            scanner.config.action(self, obj)
        self.attach_info = venusian.attach(wrapped, callback)
        return wrapped


class DirectiveAbbreviation(object):
    def __init__(self, directive):
        self.directive = directive

    def __call__(self, **kw):
        return self.directive.clone(**kw)


class Config(object):
    """Contains and executes configuration actions.

    Morepath configuration actions consist of decorator calls on
    :class:`App` instances, i.e. ``@app.view()`` and
    ``@app.model()``. The Config object can scan these configuration
    actions in a package. Once all required configuration is scanned,
    the configuration can be committed. The configuration is then
    processed, associated with :class:`morepath.config.Configurable`
    objects (i.e. :class:`App` objects), conflicts are detected,
    overrides applied, and the configuration becomes final.

    Once the configuration is committed all configured Morepath
    :class:`App` objects are ready to be served using WSGI.

    See :func:`setup`, which creates an instance with standard
    Morepath framework configuration. See also :func:`autoconfig` and
    :func:`autosetup` which help automatically load configuration from
    dependencies.
    """
    def __init__(self):
        self.configurables = []
        self.actions = []
        self.count = 0

    def scan(self, package=None, ignore=None):
        """Scan package for configuration actions (decorators).

        Register any found configuration actions with this
        object. This also includes finding any
        :class:`morepath.config.Configurable` objects.

        :param package: The Python module or package to scan. Optional; if left
          empty case the calling package will be scanned.
        :ignore: A Venusian_ style ignore to ignore some modules during
          scanning. Optional.
        """
        if package is None:
            package = caller_package()
        scanner = venusian.Scanner(config=self)
        scanner.scan(package, ignore=ignore)

    def configurable(self, configurable):
        """Register a configurable with this config.

        This is normally not invoked directly, instead is called
        indirectly by :meth:`scan`.

        A :class:`App` object is a configurable.

        :param: The :class:`morepath.config.Configurable` to register.
        """
        self.configurables.append(configurable)

    def action(self, action, obj):
        """Register an action and obj with this config.

        This is normally not invoked directly, instead is called
        indirectly by :meth:`scan`.

        A Morepath directive decorator is an action, and obj is the
        function that was decorated.

        :param: The :class:`Action` to register.
        :obj: The object to perform action on.
        """
        action.order = self.count
        self.count += 1
        self.actions.append((action, obj))

    def prepared(self):
        """Get prepared actions before they are performed.

        The preparation phase happens as the first stage of a commit.
        This allows configuration actions to complete their
        configuration, do error checking, or transform themselves into
        different configuration actions.

        This calls :meth:`Action.prepare` on all registered configuration
        actions.

        :returns: An iterable of prepared action, obj combinations.
        """
        for action, obj in self.actions:
            for prepared, prepared_obj in action.prepare(obj):
                yield (prepared, prepared_obj)

    def commit(self):
        """Commit all configuration.

        * Clears any previous configuration from all registered
          :class:`morepath.config.Configurable` objects.
        * Prepares actions using :meth:`prepared`.
        * Configuration conflicts within configurables are detected.
        * The configuration of configurable objects that extend
          each other is merged.
        * Finally all configuration actions are performed, completing
          the configuration process.

        This method should be called only once during the lifetime of
        a process, before the configuration is first used. After this
        the configuration is considered to be fixed and cannot be
        further modified. In tests this method can be executed
        multiple times as it will automatically clear the
        configuration of its configurables first.
        """
        # clear all previous configuration; commit can only be run
        # once during runtime so it's handy to clear this out for tests
        for configurable in self.configurables:
            configurable.clear()

        for action, obj in self.prepared():
            action.configurable.action(action, obj)

        configurables = sort_configurables(self.configurables)

        for configurable in configurables:
            configurable.prepare()

        for configurable in configurables:
            configurable.perform()


def sort_configurables(configurables):
    """Sort configurables topologically by extends.
    """
    result = []
    marked = set()

    def visit(n):
        if n in marked:
            return
        for m in n.extends:
            visit(m)
        marked.add(n)
        result.append(n)
    for n in configurables:
        visit(n)
    return result
