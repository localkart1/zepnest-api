"""GraphQL alias: ``Ticket`` is the ``bookings`` table (see ``booking``)."""

from api.models.booking import Booking as Ticket

__all__ = ["Ticket"]
