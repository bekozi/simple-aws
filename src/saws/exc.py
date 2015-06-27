class SimpleAwsException(Exception):
    pass


class InstanceNameNotAvailable(SimpleAwsException):
    pass


class RequiredVariableMissing(SimpleAwsException):
    pass