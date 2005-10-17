"""Job queue implemented using threads.
"""
import logging, threading, Queue

class Job:
    """Abstract unit of work, consists of a callable and arguments"""
    def __init__(self, id, func, *args, **kwargs):
        self.id     = id
        self.func   = func
        self.args   = args[:]
        self.kwargs = kwargs.copy()

    def __call__(self):
        return self.func(*self.args, **self.kwargs)

    def __repr__(self):
        return "{%s} %s() %s, %s" % (self.id, self.func, self.args, self.kwargs)

class JobQueue:

    def __init__(self, pool_size=3):
        """Initialize the queue with a worker class and a pool size"""
        self.log             = logging.getLogger("%s"%self.__class__.__name__)
        self.workers         = [Worker(name=x, pool=self) for x in range(pool_size)]
        self.jobs            = Queue.Queue()
        self.finished_jobs   = Queue.Queue()
        self.failed_jobs     = Queue.Queue()
        self.should_stop     = threading.Event()
        self.stopped         = threading.Event()
        self.stop_when_empty = False

        self.stopped.clear()
        self.should_stop.clear()
        self.log.debug("Job queue starting up")
        for w in self.workers: w.start()

    def setStopWhenEmpty(self, fl):
        self.stop_when_empty = fl

    def queueJobs(self, jobs):
        """Add jobs onto the end of the queue."""
        for j in jobs: self.jobs.put(j)

    def pause(self):
        """Pause all worker threads."""
        for w in self.workers: w.pause()

    def resume(self):
        """Resume all worker threads from pause."""
        for w in self.workers: w.resume()

    def stop(self):
        """Flag that the job queue should stop running ASAP."""
        if not self.should_stop.isSet():
            self.should_stop.set()
            for w in self.workers: w.stop()
            self.stopped.set()

    def fetchJob(self):
        """Attempt to fetch and return a job.  When none left, this returns 
        None and calls self.stop()"""
        if not self.jobs.empty():
            try: 
                return self.jobs.get(True, 0.1)
            except Queue.Empty: 
                return None
        else:
            if self.stop_when_empty: self.stop()
            return None

    def submitResult(self, worker, job, result):
        """Called by a worker to submit result back to the queue."""
        self.finished_jobs.put((job, result))
        self.log.debug("Job finished %s" % job)

    def submitException(self, worker, job, result):
        """Called by a worker to submit result back to the queue."""
        self.failed_jobs.put((job, result))
        self.log.error("Job failed: %s because of %s" % (job, result))

class Worker(threading.Thread):

    def __init__(self, name, pool):
        threading.Thread.__init__(self)
        self.setName(name)
        self.log          = logging.getLogger("%s"%self.__class__.__name__)
        self.pool         = pool
        self.should_stop  = threading.Event()
        self.should_pause = threading.Event()
        self.has_finished = threading.Event()
        self.job          = None
        
    def stop(self):
        self.should_stop.set()
        self.has_finished.wait()

    def pause(self):
        self.should_pause.set()

    def resume(self):
        self.should_pause.clear()

    def run(self):
        self.log.debug("Worker %s running" % self.getName())
        self.should_stop.clear()
        while not self.should_stop.isSet():
            if self.should_pause.isSet():
                time.sleep(0.1)
            else:
                self.job = self.pool.fetchJob()
                if self.job:
                    self.log.debug("Worker %s accepted job" % self.getName())
                    self.has_finished.clear()
                    try:
                        self.pool.submitResult(self, self.job, self.job())
                    except KeyboardInterrupt:
                        raise
                    except Exception, exc:
                        self.pool.submitException(self, self.job, exc)
                    self.job = None
                    self.has_finished.set()

