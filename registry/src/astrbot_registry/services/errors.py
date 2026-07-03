"""Domain exceptions raised by registry services."""


class RegistryError(Exception):
    status_code = 400


class NotFoundError(RegistryError):
    status_code = 404


class ConflictError(RegistryError):
    status_code = 409


class InvalidStateError(RegistryError):
    status_code = 400


class ValidationError(RegistryError):
    status_code = 400
