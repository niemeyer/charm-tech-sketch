Charm Directory and File Structure
==================================

A typical charm would have the following parts:

* ``config.yaml`` and ``metadata.yaml``;
* ``hooks`` directory with **symlinks corresponding to event names**. The
  symlinks point to a file to a python file ``run_main.py`` that:
  * extends python module search path to include the ``lib`` directory;
  * calls an entrypoint function from ``entrypoint.py``;
* ``lib/juju/framework.py`` - contains the charm framework code;
* ``lib/juju/entrypoint.py`` contains the code needed to:
  * **initialize** the charm framework for a given hook invocation;
  * **create** the **in-memory state** of the charm
    * in-memory state includes observers, emitters, persisted local state
      (handled by the framework) and Juju model state snapshot parts they care
      about (the **world view**);
    * a module-level ``Charm`` class definition from ``lib/charm.py`` provided
      by a charm author is used.
  * **re-emit** any **deferred** events;
  * **emit** the **new** Juju-originating event for the current hook invocation;
  * **commit** (persist) the framework state.
* ``lib/juju/charm.py`` - contains a base class for other charm class
  implementations;
* ``lib/charm.py`` - contains a concrete implementation of a charm;
  * the charm class can have any name;
  * a module-level ``Charm = YourClassName`` variable needs to be present for
  * ``entrypoint.py`` code to work;
* ``lib/mysql_requires_endpoint.py`` - contains an endpoint class
  implementation which handles events specific to a given endpoint from
  ``metadata.yaml``;
  * modules like this can be placed under ``lib`` or child directories in as a
    developer sees fit.

Example
-------

.. code-block:: bash

    charms/mysql/
    ├── config.yaml
    ├── hooks
    │   ├── config-changed -> run_main.py
    │   ├── install -> run_main.py
    │   ├── leader-elected -> run_main.py
    │   ├── leader-settings-changed -> run_main.py
    │   ├── run_main.py
    │   ├── mysql-relation-broken -> run_main.py
    │   ├── mysql-relation-changed -> run_main.py
    │   ├── mysql-relation-departed -> run_main.py
    │   ├── mysql-relation-joined -> run_main.py
    │   ├── post-series-upgrade -> run_main.py
    │   ├── pre-series-upgrade -> run_main.py
    │   ├── start -> run_main.py
    │   ├── stop -> run_main.py
    │   ├── update-status -> run_main.py
    │   └── upgrade-charm -> run_main.py
    ├── lib
    │   ├── charm.py
    │   ├── __init__.py
    │   ├── juju
    │   │   ├── charm.py
    │   │   ├── entrypoint.py
    │   │   ├── framework.py
    │   │   └── __init__.py
    │   └── mysql_requires_endpoint.py
    └── metadata.yaml
