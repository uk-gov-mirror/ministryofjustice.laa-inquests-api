from enum import StrEnum


class ReportType(StrEnum):
    CLAIMS_BACKLOG = "Claims Backlog"
    APPLICATIONS_BACKLOG = "Applications Backlog"
    PAYMENT_EXTRACT = "Payment Extract"
    AUDIT_TRAIL = "User Audit Trail"


class ApplicationPageType(StrEnum):
    OVERVIEW = "overview"
    CERTIFICATE = "certificate"
