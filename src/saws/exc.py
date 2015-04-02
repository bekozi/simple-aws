class SimpleAwsException(Exception):
    pass


class InstanceNameNotAvailable(SimpleAwsException):
    pass