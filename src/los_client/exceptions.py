class LOSClientException(Exception):
    pass

class SolverException(LOSClientException):
    pass

class SolverParseResultFailed(SolverException):
    pass

class SolverNotFound(SolverException):
    pass
