# Exceptions

The following exception classes are used by `sitemessage` (`sitemessage.exceptions` module):

* **SiteMessageError** — Base class for sitemessage errors.
* **SiteMessageConfigurationError** — This error is raised on configuration errors.
* **UnknownMessageTypeError** — This error is raised when there's a try to access an unknown message type.
* **MessengerException** — Base messenger exception.
* **UnknownMessengerError** — This error is raised when there's a try to access an unknown messenger.
* **MessengerWarmupException** — This exception represents a delivery error due to a messenger warm up process failure.
