"""Job queue implemented using threads.
"""
import logging, threading, Queue
from Queue import Queue, Empty

# Global registry of all job queues
all_job_queues = []

def enumerate():
    return [ x for x in all_job_queues if x.isAlive() ]

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

    FETCH_JOB_TIMEOUT    = 1.0
    FETCH_RESULT_TIMEOUT = 1.0
    
    def __init__(self, pool_size=3):
        """Initialize the queue with a worker class and a pool size"""
        self.log             = logging.getLogger("%s"%self.__class__.__name__)
        self.workers         = [Worker(name=x, pool=self) for x in range(pool_size)]
        self.jobs            = Queue()
        self.finished_jobs   = Queue()
        self.failed_jobs     = Queue()
        self.should_stop     = threading.Event()
        self.stopped         = threading.Event()
        self.stop_when_empty = False

        self.stopped.clear()
        self.should_stop.clear()
        self.log.debug("Job queue starting up")
        for w in self.workers: w.start()

        all_job_queues.append(self)

    def isAlive(self):
        return not self.stopped.isSet()

    def hasResults(self):
        return not (self.failed_jobs.empty() and self.finished_jobs.empty())

    def activeWorkers(self):
        return [x for x in self.workers if not x.isIdle()]

    def setStopWhenEmpty(self, fl):
        self.stop_when_empty = fl

    def append(self, job):
        """Queue up a single job."""
        self.jobs.put(job)

    def extend(self, jobs):
        """Queue up a list of jobs."""
        for job in jobs: self.append(job)

    def pause(self):
        """Pause all worker threads."""
        for w in self.workers: w.pause()

    def resume(self):
        """Resume all worker threads from pause."""
        for w in self.workers: w.resume()

    def stop(self):
        """Flag that the job queue should stop running ASAP."""
        if not self.should_stop.isSet():
            self.log.debug("Queue stop() called")
            self.should_stop.set()
            for w in self.workers: w.stop()
            self.stopped.set()

    def fetchJob(self):
        """Attempt to fetch and return a job.  When none left, this returns 
        None and calls self.stop()"""
        try:
            return self.jobs.get(True, self.FETCH_JOB_TIMEOUT)
        except:
            if self.stop_when_empty:
                # Only stop on empty queue when all workers are idle.
                if not self.activeWorkers(): self.stop()
            return None

    def fetchResult(self):
        try: return self.failed_jobs.get(True, 0.1)
        except Empty: pass
        try: return self.finished_jobs.get(True, self.FETCH_RESULT_TIMEOUT)
        except Empty: return None

    def submitResult(self, worker, job, result):
        """Called by a worker to submit result back to the queue."""
        self.finished_jobs.put((job, result))
        self.log.debug("Job finished %s" % job)

    def submitException(self, worker, job, result):
        """Called by a worker to submit result back to the queue."""
        self.failed_jobs.put((job, result))
        self.log.error("Job failed: %s because of %s" % (job, result))

class Worker(threading.Thread):

    def __init__(self, name, pool, daemon=True):
        threading.Thread.__init__(self)
        self.setName(name)
        self.setDaemon(daemon)

        self.log          = logging.getLogger("%s"%self.__class__.__name__)
        self.pool         = pool
        self.should_stop  = threading.Event()
        self.should_pause = threading.Event()
        self.job          = None
        self.idle         = threading.Event()
        self.idle.set()
        
    def stop(self):
        self.should_stop.set()
        # TODO: Make sure this is the best thing to do, or should join() be an atexit handler?
        if self is not threading.currentThread(): 
            self.join()

    def pause(self):
        self.should_pause.set()

    def resume(self):
        self.should_pause.clear()

    def isIdle(self):
        return self.idle.isSet()

    def run(self):
        self.log.debug("Worker %s running" % self.getName())
        self.should_stop.clear()
        while not self.should_stop.isSet():
            if self.should_pause.isSet():
                time.sleep(0.5)
            else:
                self.job = self.pool.fetchJob()
                if self.job:
                    self.log.debug("Worker %s accepted job" % self.getName())
                    self.idle.clear()
                    try:
                        self.pool.submitResult(self, self.job, self.job())
                    except KeyboardInterrupt:
                        raise
                    except Exception, exc:
                        self.pool.submitException(self, self.job, exc)
                    self.job = None
                    self.idle.set()

