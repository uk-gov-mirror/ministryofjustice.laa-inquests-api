
# Ticket description
## User story
**As** a member of the Fraud and Assurance team,

**I want** a data extract showing auditable user and system activity across the service,

**So that** I can understand what activity took place, who performed it and when, to support assurance and fraud investigations.

## Context
The extract provides an audit trail of activity across all cases, including Case History events, application views and report downloads.

The full report specification, including fields, qualifying events, event titles, descriptions and reporting rules, is maintained in report specification

This story implements that specification.

## Non-functional requirements

1. Volume requirement to be confirmed. Current planning assumption: approximately 11,000 cases per year. Event volume within a 30-day reporting period is not yet known and will need to be estimated.
2. Report content and behaviour must conform to the [**User Audit Trail specification**](https://dsdmoj.atlassian.net/wiki/spaces/LI/pages/6320489479/User+audit+trail). Event titles and descriptions must use the values defined in the [**Event Catalogue**](https://dsdmoj.atlassian.net/wiki/spaces/LI/pages/6183453175/Event+catalogue).
3. Report file name should conform to LAA standards defined here: [https://dsdmoj.atlassian.net/wiki/x/ZoEvdwE](https://dsdmoj.atlassian.net/wiki/x/ZoEvdwE)

## Out of scope

1. Access control, covered separately.
2. Report download functionality, covered separately.
3. Scheduling and automated delivery.
4. Retention and S3 storage.
5. Email or Teams delivery.
6. Failure alerting.
7. Search, document viewing and general service access or login activity.
8. Bespoke dashboards or visualisations.
9. Entra ID as a standard extract field.

## Technical note
The report must include all events from the history_event table and audit records created by:

- [IDDS-748 – Log application views](https://dsdmoj.atlassian.net/browse/IDDS-748)
- [IDDS-754 – Log report generation](https://dsdmoj.atlassian.net/browse/IDDS-754)

# Acceptance criteria
✅ AC1 Given qualifying audit events exist within the selected date range

When the User Audit Trail extract is generated

Then the extract:

Includes all qualifying events defined in the report specification that exist at the point of generation.

Includes events across all cases.

Includes events performed by internal and external users and system-generated events.

Contains the fields, event titles and descriptions defined in the report specification.

Uses the user's email address for user-performed events and System for system-generated events.

Populates provider firm details where applicable and held by the service.

Is a valid CSV containing a header row and one row per qualifying event.

Orders records by event date and time.

Can be filtered, sorted and analysed using standard spreadsheet tools.

Matches the IDDS file naming convention

✅ AC2 Date range

Given a user requests an extract

When they select the reporting period

Then:

The reporting period is based on event date, inclusive.

Each reporting day runs from 00:00:00 to 23:59:59 UTC.

The selected date range must not exceed 30 days.

✅ AC3 No records

Given the extract is generated

When no qualifying events exist within the selected date range

Then a valid CSV is produced containing the expected column headers and no data rows.

❌ AC4 Given the extract is requested

When it cannot be generated successfully

Then:

No incomplete, partial or misleading CSV is produced.

No extract output is made available.

Sufficient error information is captured to support investigation and resolution.

# Additional comments
## 1
@Heather Fleming  to look into the answer for: 

 We're going to include the user email address but would the Entra ID of the user be useful in addition to this to you? This ID will be unique to the user and will not change even if the email address changes.

Do you want the full description of an event as shown in the user interface in the service, or would you prefer this broken down in the way which we store this information in the back-end?

Do you need Firm name or number associated with provider actions if we're able to provide this?

## 2
Responses to these questions from Saffa: 

We would typically use the email address to corroborate the firm that the user was meant to be acting on behalf of, so would typically find that more helpful than a unique ID. However, if the unique user ID is kept and we can ask for it, that would be helpful. I'm thinking of scenarios where we may need to trace previous email accounts associated with the same ID. - Sounds like this isn’t needed in a regular report.

If I understand the question correctly, a user-interface version might be more user-friendly for us. Is it possible to see an example of each? - response after examples provided: That's much of a muchness really, so am happy to go with whatever is actually easier for the team to progress with. If pushed for a choice, I'd go for the second one though

Yes. At least this answer was straightforward!

## 3
@Heather Fleming I have some follow up questions:

Event description: Can you confirm that, following the examples shown to Saffa, we should use the back-end/stored event description for the extract?

Firm details: Can you confirm whether both firm name and office account number are expected for provider actions, where held, or whether one of these is sufficient?

Entra ID: Saffa said the unique user ID could be useful for exceptional investigations but is not needed in the regular report. Do we need to capture a separate requirement for how Fraud and Assurance could request or retrieve Entra ID when needed?

Volume: Do we have any indication of the expected maximum number of case history events within a 30-day period, so the NFR can be completed?

## 4
@Rachel Moody 

Stored event description, she’d prefer the user-friendly version as you can see in the update I added.

Saffa confirmed above that she’d like both.

No, if this is required then it would be a one-off request (especially for MVP), this should be handled as such when it is required.

No idea, we're going to have to estimate (very roughly) based on the anticipated volume of 11,000 cases per year.

# Atlassian docs
## User audit trail
Purpose
The User Audit Trail extract provides Fraud & Assurance with a downloadable record of auditable activity across the service, showing what activity took place, who performed it and when.

The extract supports assurance and fraud investigations by providing a record of relevant user and system activity across cases.

Frequency
Weekly

Users can select a reporting period of up to 30 days.

Report format
The report is provided as a CSV file so that the data can be filtered, sorted and analysed using tools such as Microsoft Excel.

The extract contains one row for each qualifying event within the selected reporting period.

Data included
Field

Description

Event title

Event title defined in the Event Catalogue

Event description

User-friendly event description defined in the  Event Catalogue

Event date

Date the event occurred

Event time

Time the event occurred

Username

Email address of the user who performed the action, or System for system-generated events

Case reference

Case reference associated with the event, where applicable

Firm name

Provider firm name for provider actions, where held

Office account number

Provider office account number for provider actions, where held

Where a field does not apply to an event, or the information is not held by the service, it will be blank.

Events included
The extract includes all qualifying Business, Communication and Case Audit events defined as in scope in the Event Catalogue.

The Event Catalogue is the source of truth for:

event reference

event title

trigger

actor

event description

resulting status

event-specific data

related events

This report specification does not duplicate those event definitions. Auditable+event+catalogue

Case Audit events, such as application views and report downloads, are included in the extract even though they are not displayed in the Case History tab. Auditable+event+catalogue

Username
For an event performed by a user, Username contains the user's email address.

For an event generated automatically by the service, Username contains:

System

Case reference
The Case reference is populated where the event relates to a specific case.

Where an event does not relate to a single case, the Case reference field is blank.

Provider information
For actions performed by a provider, the following information is included where held by the service:

Firm name

Office account number

These fields are blank where provider information does not apply or is not held.

Reporting period
The reporting period is based on the date the event occurred.

Dates are inclusive.

Each reporting day runs from 00:00:00 to 23:59:59 UTC.

The selected reporting period must not exceed 30 days.

Records are ordered by event date and time.

The extract contains all qualifying events that exist at the point the report is generated. IDDS-731

No records
Where no qualifying events exist within the selected reporting period, a valid CSV is produced containing the expected column headers and no data rows.

Report generation failure
If the report cannot be generated successfully:

no incomplete, partial or misleading CSV is produced

no extract output is made available

sufficient error information is captured to support investigation and resolution IDDS-731

Out of scope
The MVP User Audit Trail does not include:

search activity

document viewing activity

general service access or login activity

Entra ID as a standard report field

dashboards or visualisations

manipulation or interpretation of the extracted data

automated scheduling or delivery of the report

## Event catalogue
Purpose
The Events Catalogue defines the auditable events recorded by the service.

It is the single source of truth for the business behaviour of each event, including:

event title

trigger conditions

actor

history description, which is the user-friendly description associated with the event

resulting status, where applicable

event-specific data

conditional logic

related events

The History Event Framework provides the reusable capability for creating, storing and displaying history entries. Individual history event stories implement the events defined in this catalogue using that framework.

Scope
The catalogue primarily contains events that are visible in the History tab.

It also records Case Audit events that are required for audit and reporting purposes but are not displayed in the History tab. These use the EVT-AUD-### reference pattern and are stored using the separate audit mechanism described in Inquests ADR 08 – Logging page views and report generation.

Operational and technical events that are not displayed in the History tab are documented separately where required.

Event fields
Event title is the concise name used to identify the event, including where the event is used in reporting.

History Description is the user-friendly description associated with the event. For History events, this is what is displayed in the service. It may contain dynamic event data.

Event Categories
Category

Reference Pattern

Purpose

Visible in History Tab

Business

EVT-BUS-###

Meaningful business events and information relating to an application or claim.

Yes

Communication

EVT-COM-###

Notifications relating to an application and claim.

Yes

Exception

EVT-EXC-###

Permanent failures requiring operational intervention.

Yes, out of scope for MVP

Operational

N/A

Technical processing events such as retries, integrations and API activity.

No

Case Audit

EVT-AUD-###

User actions such as viewing cases, downloading reports and searches.

No. See Inquests ADR 08.

Identity, authentication, role and permission events are managed outside the service and are not included in this catalogue.

Business Events
X-functional
Ref

Event title

Trigger

Actor

History Description

Resulting Status

Event Data

Related Events

Notes

EVT-BUS-X-001

Case note added

Caseworker successfully saves a case note

Caseworker

Case note added

No change

Case note text

None

 

Application Events (EVT-BUS-APP-)
Ref

Event title

Trigger

Actor

History Description

Resulting Status

Event Data

Related Events

Notes

001

Application submitted

Application successfully submitted

Provider

Application received

Submitted

None

EVT-COM-APP-001

 

002

Application assessment complete

Assessment completed

Caseworker

Application <decision>

Granted / Refused

Refusal reason; Refusal justification, refused only

EVT-COM-APP-004

Decision determines description and event data

003

Certificate created

Certificate generated

System

Certificate created

Granted

 

EVT-COM-APP-002, EVT-COM-APP-003

Link to certificate

004

Interested party updated

Interested party added or removed

Caseworker

Interested parties updated from <old value> to <new value>

No status change

Public body

None

 

Claim Events (EVT-BUS-CLM-)
Ref

Event title

Trigger

Actor

History Description

Resulting Status

Event Data

Related Events

Notes

001

Claim submitted

Claim successfully submitted

Provider

<claim type> claim received : <claim reference>

Submitted

Claim type

EVT-COM-CLM-002

 

002

Claim assessment complete

Assessment completed

Caseworker

<claim type> claim <decision> : <claim reference>

Paid in Full / Rejected / Adjusted

Claim type; Claim decision; Decision justification

EVT-COM-CLM-001

Justification required for Rejected and Adjusted decisions

003

POA auto-approved

Auto-approval criteria met

System

POA claim <claim reference> auto-approved

Approved

Claim reference

None

 

004

POA auto-rejected

Auto-rejection criteria met

System

POA claim <claim reference> auto-rejected

Rejected

Claim reference

None

 

Events 001 and 002 updated September 2026 to include claim reference number following the claim reference work. Auditable+event+catalogue

Communication Events
Application Notifications (EVT-COM-APP-)
Ref

Event title

Trigger

Actor

History Description

Resulting Status

Event Data

Related Events

Notes

001

Application submission confirmation

Application submitted notification sent

System

Application submission confirmation sent

N/A

Recipient: Provider; Channel: Email

EVT-BUS-APP-001

 

002

Application granted (Email)

Certificate created notification sent

System

Application granted email sent

N/A

Recipient: Provider; Channel: Email

EVT-BUS-APP-003

 

003

Application granted (Letter)

Certificate created notification sent

System

Application granted letter sent

N/A

Recipient: Client; Channel: Letter

EVT-BUS-APP-003

 

004

Application refused

Application assessment complete notification sent

System

Application refused email sent

N/A

Recipient: Provider; Channel: Email

EVT-BUS-APP-002

 

 

Claim Notifications (EVT-COM-CLM-)
Ref

Event title

Trigger

Actor

History Description

Resulting Status

Event Data

Related Events

Notes

001

Claim submission confirmation

Claim submitted notification sent

System

Claim submission confirmation sent

N/A

Recipient: Provider; Channel: Email

EVT-BUS-CLM-001

 

002

Claim approved

Claim assessment complete notification sent

System

Claim approved email sent

N/A

Recipient: Provider; Channel: Email

EVT-BUS-CLM-002

 

003

Claim Rejected

Claim Rejected by the caseworker

System

Claim rejection email sent

Rejected

Recipient: Provider; Channel: Email

EVT-COM-CLM-003

Claim reject letter sent with details and reasons

 

Exception Events (EVT-EXC-)
Ref

Event title

Trigger

Actor

History Description

Resulting Status

Event Data

Related Events

Notes

001

Permanent notification failure

Notification permanently fails

System

Notification delivery failed

N/A

Notification details

None

Out of MVP scope

 

Audit Events (EVT-AUD-)
Audit events are recorded for assurance and reporting purposes but are not displayed in the History tab.

Ref

Event title

Trigger

Actor

History Description

Resulting Status

Event Data

Related Events

Notes

Ref

Event title

Trigger

Actor

History Description

Resulting Status

Event Data

Related Events

Notes

001

Application viewed

User successfully opens an application

Internal user

Application viewed

No change

Application reference

None

 

002

Report downloaded

User successfully generates and downloads an MI report

Internal user

<report name> downloaded

No change

Report name; reporting period from date; reporting period to date

None

 