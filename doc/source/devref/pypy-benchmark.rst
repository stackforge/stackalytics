================
 PyPy benchmark
================

This article is about running Stackalytics in PyPy and trying to put some
numbers on it. 

Problem to be solved
====================

Stackalytics follows shared-nothing all-in-memory architecture. You don't need
DB, you don't need weird external locks. All you need is a processor pumping
raw data from the outside into an Memcached instance and a web worker(s) that
happily suck that data into their memory, build indexes over it and then for
every request from a user calculate necessary stats and send them to a happy
user.

By the rules of Game of Life, moderate number of happy users produce more users
and soon enough there will be too much users and they won't be very happy
because they'll have to wait for one and only process to respond.

So why not create more processes? Let's say we have a fine machine with 8Gb
RAM. How would that be spent:

 * ~800-900 M takes memcached that holds all data records in pickled format;
 * processor would take about the same amount of memory once in a while;
 * every web worker would take about 2.5 Gb to hold these records in memory in
   a huge number of dicts.

As you can see, you can't run more than 2 web workers simultaneously on such
machine because you simply won't get enough memory. After some poking around
those 2.5 Gb were reduced to 1.5 Gb by replacing all those dicts with
namedtuples. Still huge 8Gb machine can hold only 3 workers without using swap
(which is turned off anyway).

So the problem is: web workers should share most of (static) memory they use.

Roads not taken
---------------

I'd like to immediatly note options that were considered but didn't work out:

Creating another service that would hold that data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This would shift the bottleneck from web workers to this new service. The stats
calculation is a CPU-bound task that is done in pure Python, so you won't be
able to process more than one request simultaneously.

Use shared memory to store that data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The problem is that you can't easily store Python objects in shared memory. You
can't even reliably store a reference to a Python object there since it would
be mapped to different virtual address in every process. So I've tried to write
up a class that would store data in shared space and on demand convert it to
Python objects. There are two problems with that:

 * the dance around converting Python objects to raw data and back is *ugly*;
 * you have to convert all data you are reading from raw format to Python
   objects every time.

Use copy-on-write sharing after fork()
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unfortunately that doesn't quite work in CPython. It stores refcount near data
itself so when you read data you also write to the same page [#py_mem]_.

Write this part in C FWIW!
~~~~~~~~~~~~~~~~~~~~~~~~~~

Oh, no. I won't give up on Python just yet ;)

Initial thoughts on the solution
--------------------------------

I want to solve this problem by:

 * improving single-process performance by using PyPy;
 * allowing sharing data in forked processes (because PyPy is smarter than
   CPython).

In the setup that is used in production web processes are managed by uWSGI. So
I'm going to use its PyPy plugin eventualy.

Setup
=====

All what follows happens on my work laptop.

System specs
------------

 * Toshiba Portege Z930
 * Intel(R) Core(TM) i5-3337U CPU @ 1.80GHz
 * 6 Gb RAM
 * Toshiba THNSNF 128 Gb SSD
 * Gentoo Linux (it's Gentoo, it's always the latest)
 * CPython 2.7.6
 * PyPy 2.3.1
 * uWSGI 2.0.5

Installation
------------

First I needed PyPy itself. Latest version in the Portage was 2.3 and it had no
option to be built with a shared library that's required for uWSGI plugin. So
I've bumped its version while adding new USE flag [#pypy_ebuild]_.

Then I needed PyPy plugin for uWSGI. It's not provided by ebuild, so I checked
out source [#uwsgi_repo]_ and built it. For those who say that Gentoo guys take
too much time to get ready::

    yorik@ytaraday uwsgi % time env UWSGI_PROFILE=pypy make
    <......>
    env UWSGI_PROFILE=pypy make  52.31s user 2.81s system 365% cpu 15.070 total

(in binary packagers' defence, PyPy took about an hour and 4G RAM to build)

While getting working virtual environment for CPython was very easy (``tox -e
py27 --notest`` did it), PyPy on Gentoo doesn't support virtualenvs
[#pypy_venv]_. I worked that around [#pypy_venv]_ and created a new shiny
virtual env for PyPy::

    $ virtualenv -p pypy .venv.pypy
    $ .venv.pypy/bin/pip install -r requirements.txt

And found out that Stackalytics depends on Paramiko that depends on PyCrypto
that does nasty things with your Python objects and so doesn't play nice with
alternative implementations [#pycrypto_shit]_ (although the fix seems to be
near [#pycrypto_shiny]_). Since Paramiko is needed for
``stackalytics-processor`` only and I want to play with web processes only,
I've commented it out in ``requirements.txt`` and everything worked fine. I'll
have to load data from a dump instead of live OpenStack infrastructure.

And... Go!
==========

(no Go language used)

I'll omit virtualenv prefixes everywhere and will use GNU version of ``time``
utility. I'll also remove uninteresting values from its output and divide
results about memory in it by 4 because of bug in the utility [#time_bug]_.

Loading dump into Memcached
---------------------------

So I have fresh empty memcached started and for every option (CPython and PyPy)
run::

    time -v stackalytics-dump -rf stackalytics.dump

This dump has been taken from production system some time ago.

CPython
~~~~~~~

Results::

        User time (seconds): 263.66
        System time (seconds): 3.76
        Percent of CPU this job got: 98%
        Elapsed (wall clock) time (h:mm:ss or m:ss): 4:30.80
        Maximum resident set size (kbytes): 16396

And Memcached oscilated around 4-5% CPU usage.

PyPy
~~~~

Results::

        User time (seconds): 144.02
        System time (seconds): 6.02
        Percent of CPU this job got: 95%
        Elapsed (wall clock) time (h:mm:ss or m:ss): 2:37.11
        Maximum resident set size (kbytes): 95248

Memcached oscilated around 10% CPU usage.

Conclusion
~~~~~~~~~~

PyPy lives up to the promise to trade your RAM for CPU. It ate 6 times more RAM
while running almost 2 times faster.

Loading data from Memcached into Vault
--------------------------------------

During its lifetime, Stackalytics web process loads all data from Memcached
into its memory. I've isolated this behaviour into small script::

    from dashboard import web, vault
    
    with web.app.test_request_context():
        vault.get_vault()

and run it under ``time`` as early::

    time -v python load_vault.py

CPython
~~~~~~~

Results::

        User time (seconds): 111.69
        System time (seconds): 1.41
        Percent of CPU this job got: 98%
        Elapsed (wall clock) time (h:mm:ss or m:ss): 1:55.07
        Maximum resident set size (kbytes): 1656044

PyPy
~~~~

Results::

        User time (seconds): 53.43
        System time (seconds): 1.84
        Percent of CPU this job got: 96%
        Elapsed (wall clock) time (h:mm:ss or m:ss): 0:57.18
        Maximum resident set size (kbytes): 2131884

Conclusion
~~~~~~~~~~

PyPy is still 2 times faster although memory overhead is unexpectedly big. With
old (dict-based) code overhead is around 8%, here it's around 30%.

Processing data
---------------

Now let's compare speed of data processing. Let's add this part to the previous
script::

    import functools, timeit

    with web.app.test_client() as c:
        f = functools.partial(c.get, '/api/1.0/stats/timeline')
        num = 100
        s = timeit.timeit(f, number=num)
        print "%.3f sec, %.6f sec per iteration" % (s, s / num)

And then to measure data processing itself instead of cache speed, comment out
line #490 with ``@decorators.cached()`` before ``timeline()`` method in
``dashboard/web.py``.

CPython
~~~~~~~

Results::

    199.418 sec, 1.994177 sec per iteration
        User time (seconds): 361.15
        System time (seconds): 3.48
        Percent of CPU this job got: 99%
        Elapsed (wall clock) time (h:mm:ss or m:ss): 6:06.79
        Maximum resident set size (kbytes): 1721696


PyPy
~~~~

Results::

    59.776 sec, 0.597760 sec per iteration
        User time (seconds): 133.19
        System time (seconds): 3.48
        Percent of CPU this job got: 98%
        Elapsed (wall clock) time (h:mm:ss or m:ss): 2:18.70
        Maximum resident set size (kbytes): 2831892


Conclusion
~~~~~~~~~~

While PyPy becomes 3.5 times faster, memory overhead reaches 65%.

Full HTTP app (with caching)
----------------------------

Now let's compare performance under uWSGI in a single-process mode. For that
I've build 2 versions of uWSGI: ``uwsgi`` using plain ``make`` and
``uwsgi-pypy`` as shown above. After starting HTTP server in uWSGI I've issued
first request to pre-warm cache (and fetch data from Memcached to process
memory)::

    curl http://127.0.0.1:8080/api/1.0/stats/timeline > /dev/null

And then ran Apache Benchmark with no concurrency::

    ab -t 30 -c 1 http://127.0.0.1:8080/api/1.0/stats/timeline

And with some concurrency::

    ab -t 30 -c 10 http://127.0.0.1:8080/api/1.0/stats/timeline

After that I checked memory usage of uWSGI process (resident set) with ``top``.

CPython
~~~~~~~

uWSGI commandline::

    uwsgi --http 0.0.0.0:8080 --wsgi dashboard.web:app --virtualenv .tox/py27

ab results (no concurrency)::

    Concurrency Level:      1
    Time taken for tests:   30.000 seconds
    Complete requests:      28069
    Failed requests:        0
    Write errors:           0
    Total transferred:      130099815 bytes
    HTML transferred:       128050778 bytes
    Requests per second:    935.63 [#/sec] (mean)
    Time per request:       1.069 [ms] (mean)
    Time per request:       1.069 [ms] (mean, across all concurrent requests)
    Transfer rate:          4235.01 [Kbytes/sec] received

    Connection Times (ms)
                  min  mean[+/-sd] median   max
    Connect:        0    0   0.0      0       0
    Processing:     1    1   0.4      1      12
    Waiting:        0    1   0.4      1      12
    Total:          1    1   0.4      1      12

    Percentage of the requests served within a certain time (ms)
      50%      1
      66%      1
      75%      1
      80%      1
      90%      1
      95%      2
      98%      2
      99%      2
     100%     12 (longest request)

ab results with concurrency::

    Concurrency Level:      10
    Time taken for tests:   30.001 seconds
    Complete requests:      35944
    Failed requests:        0
    Write errors:           0
    Total transferred:      166600440 bytes
    HTML transferred:       163976528 bytes
    Requests per second:    1198.11 [#/sec] (mean)
    Time per request:       8.346 [ms] (mean)
    Time per request:       0.835 [ms] (mean, across all concurrent requests)
    Transfer rate:          5423.08 [Kbytes/sec] received

    Connection Times (ms)
                  min  mean[+/-sd] median   max
    Connect:        0    0   0.0      0       4
    Processing:     1    8   2.1      8      35
    Waiting:        1    8   2.1      8      35
    Total:          1    8   2.1      8      35

    Percentage of the requests served within a certain time (ms)
      50%      8
      66%      8
      75%      8
      80%      8
      90%     10
      95%     12
      98%     16
      99%     17
     100%     35 (longest request)

Memory usage after benchmark: 1650M

PyPy
~~~~

uWSGI commandline::

    uwsgi-pypy --http 0.0.0.0:8080 --pypy-wsgi dashboard.web:app --pypy-home .venv.pypy

ab results (no concurrency)::

    Concurrency Level:      1
    Time taken for tests:   29.770 seconds
    Complete requests:      50000
    Failed requests:        0
    Write errors:           0
    Total transferred:      231750000 bytes
    HTML transferred:       228100000 bytes
    Requests per second:    1679.52 [#/sec] (mean)
    Time per request:       0.595 [ms] (mean)
    Time per request:       0.595 [ms] (mean, across all concurrent requests)
    Transfer rate:          7602.12 [Kbytes/sec] received

    Connection Times (ms)
                  min  mean[+/-sd] median   max
    Connect:        0    0   0.0      0       1
    Processing:     0    1   1.4      0     127
    Waiting:        0    0   1.3      0     126
    Total:          0    1   1.4      0     127

    Percentage of the requests served within a certain time (ms)
      50%      0
      66%      0
      75%      1
      80%      1
      90%      1
      95%      1
      98%      2
      99%      3
     100%    127 (longest request)

ab results with concurrency::

    Concurrency Level:      10
    Time taken for tests:   16.227 seconds
    Complete requests:      50000
    Failed requests:        0
    Write errors:           0
    Total transferred:      231750000 bytes
    HTML transferred:       228100000 bytes
    Requests per second:    3081.19 [#/sec] (mean)
    Time per request:       3.245 [ms] (mean)
    Time per request:       0.325 [ms] (mean, across all concurrent requests)
    Transfer rate:          13946.60 [Kbytes/sec] received

    Connection Times (ms)
                  min  mean[+/-sd] median   max
    Connect:        0    0   0.0      0       2
    Processing:     1    3   1.4      3      25
    Waiting:        1    3   1.4      3      25
    Total:          1    3   1.4      3      25

    Percentage of the requests served within a certain time (ms)
      50%      3
      66%      3
      75%      3
      80%      3
      90%      5
      95%      6
      98%      8
      99%      9
     100%     25 (longest request)

Memory usage after benchmark: 2300M

Conclusion
~~~~~~~~~~

PyPy keep steady memory overhead of 40% and performance gain of 2-2.6x.

uWSGI with threading
--------------------

Let's see what would happend if Stackalytics become thread-safe. It is not
currently thread-safe but for one request that won't trigger cache or vault
update it's safe enough.

I've added ``--threads 3`` to each of uWSGI command lines (I've got 4 cores and
one of them runs ab) and ran ab with concurrency.

CPython
~~~~~~~

ab results::

    Concurrency Level:      10
    Time taken for tests:   30.001 seconds
    Complete requests:      25871
    Failed requests:        0
    Write errors:           0
    Total transferred:      119920816 bytes
    HTML transferred:       118032087 bytes
    Requests per second:    862.34 [#/sec] (mean)
    Time per request:       11.596 [ms] (mean)
    Time per request:       1.160 [ms] (mean, across all concurrent requests)
    Transfer rate:          3903.54 [Kbytes/sec] received

    Connection Times (ms)
                  min  mean[+/-sd] median   max
    Connect:        0    0   0.0      0       2
    Processing:     1   12   4.7     10      54
    Waiting:        1   10   4.1      9      51
    Total:          1   12   4.7     10      54

    Percentage of the requests served within a certain time (ms)
      50%     10
      66%     11
      75%     12
      80%     13
      90%     18
      95%     22
      98%     26
      99%     30
     100%     54 (longest request)

PyPy
~~~~

ab results::

    Concurrency Level:      10
    Time taken for tests:   15.551 seconds
    Complete requests:      50000
    Failed requests:        0
    Write errors:           0
    Total transferred:      231750000 bytes
    HTML transferred:       228100000 bytes
    Requests per second:    3215.24 [#/sec] (mean)
    Time per request:       3.110 [ms] (mean)
    Time per request:       0.311 [ms] (mean, across all concurrent requests)
    Transfer rate:          14553.36 [Kbytes/sec] received

    Connection Times (ms)
                  min  mean[+/-sd] median   max
    Connect:        0    0   0.0      0       1
    Processing:     1    3   1.9      2      41
    Waiting:        0    3   1.8      2      39
    Total:          1    3   1.9      3      41

    Percentage of the requests served within a certain time (ms)
      50%      3
      66%      3
      75%      3
      80%      4
      90%      5
      95%      6
      98%      8
      99%     11
     100%     41 (longest request)

Conclusion
~~~~~~~~~~

PyPy shows no performance penalty from multithreading but no improvement
either. CPython slows down by about 40%. That's expected since PyPy is known
for better multithreading support bug still has that GIL.

Finally - multiprocessing
-------------------------

While PyPy shows good performance improvement as it is, the goal was to use
multiple workers sharing one set of data in memory. As I've shown
multithreading won't give any performance boost so processes are the way to go.

We'll be measuring memory first, so I've pushed everything I could out to
swap::

    dd if=/dev/zero conv=block cbs=4096M of=/dev/null bs=4096M count=1

to let two processes fit into my humble RAM.

I'll show total memory usage (taken from ``htop``) before and after two
requests that would land to different processes.

uWSGI forks processes after app is loaded, so I've added fetching of data from
Memcached to the end of ``dashboard/web.py``::

    with app.test_request_context():
        vault.get_vault()

CPython
~~~~~~~

Before starting uWSGI memory usage was: 1212 Mb

The first process loads data, memory usage steadily raises up to: 2842 Mb.
Process forks, memory usage remains the same althoug there're two processes
with 1730M residental set.

After first cURL call we hit the second process and memory usage jups up to
3270 Mb. Second process has 30M more residental set.

After third cURL call we hit the first process, it gains its 30M and total
memory usage raises accordingly.

PyPy
~~~~

Now let's kill uWSGI process and start the same process with PyPy. We start
with memory usage at 1222 Mb.

Data is loaded, memory usage: 3288 Mb. Two processes have 2059 Mb residental
set.

I hit the first process, it's residental set gains about 112M and memory usage
raises to 3400 Mb.

After two more tries I hit the second process. Total memory usage raises up to
3485 Mb, second process gets 100M mor residental set.

Conclusion
~~~~~~~~~~

CPython is not that good at sharing memory: about 400M are not really shared
between processes after the first read in one of processes. PyPy shows it's
beauty: all data is shared, only newly allocated memory stays unique for every
process.

Overall results
===============

PyPy shows significant performance improvement over CPython with the cost of
significant memory overhead but that memory can be effectively shared between
processes by using uWSGI's smart forking. Memory sharing can be improved
further by prewarming cache and/or using adaptive forking under load when fork
will happen only when needed and every new process will receive all cached data
from the lifetime of the parent process.

References
==========

.. [#py_mem] http://www.youtube.com/watch?v=twQKAoq2OPE

.. [#pypy_ebuild] https://bugs.gentoo.org/show_bug.cgi?id=513014

.. [#uwsgi_repo] https://github.com/unbit/uwsgi

.. [#pypy_venv] https://bugs.gentoo.org/show_bug.cgi?id=462306

.. [#pycrypto_shit] https://bitbucket.org/pypy/pypy/issue/997/

.. [#pycrypto_shiny] https://github.com/dlitz/pycrypto/pull/59#issuecomment-37843491

.. [#time_bug] http://stackoverflow.com/a/10132854/238308
