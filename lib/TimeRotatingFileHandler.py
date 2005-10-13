import os, time, logging, logging.handlers

class TimeRotatingFileHandler(logging.FileHandler):
    def __init__(self, filename_tmpl, mode="a"):
        """
        Given a strfime template for filenames, use it to construct a
        filename for logging from the current time.  A stream will be
        opened with this filename, to which log messages will be
        written.

        For each log emission, the strfime template will be filled
        using the current time.  If that new filename differs from the
        current one being written, the current stream will be closed,
        and a new one opened to the new filename.

        This has the effect of rotating log writes to timestamped log
        filenames.
        """
        if filename_tmpl.startswith('/'):
            self.filename_tmpl = filename_tmpl
        else:
            self.filename_tmpl = "%s/%s" % (os.getcwd(), filename_tmpl)

        self.filename      = time.strftime(self.filename_tmpl)
        logging.FileHandler.__init__(self, self.filename, mode)
        #os.chmod(self.filename, 0664)

        self.stream = None

    def __del__(self):
        """
        Clean up after ourselves.
        """
        self.close()

    def close(self):
        if self.stream is not None:
            self.stream.close()

    def doRollover(self, new_filename):
        """
        Given a new filename, close the current stream and open a new one.
        """
        if not self.stream is None:
            self.stream.close()
            del self.stream
        self.filename = new_filename
        self.stream   = open(self.filename, "a")
        #os.chmod(self.filename, 0664)

    def emit(self, record):
        """
        Emit a record, first checking whether or not a new log needs
        to be opened.
        """
        # Check to see if we need a new timestamped filename
        new_filename = time.strftime(self.filename_tmpl)        
        if self.filename != new_filename or self.stream is None:
            self.doRollover(new_filename)
        logging.FileHandler.emit(self, record)

logging.handlers.TimeRotatingFileHandler = TimeRotatingFileHandler
