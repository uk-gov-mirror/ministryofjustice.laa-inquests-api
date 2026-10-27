import random
from collections import Counter
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from freezegun import freeze_time
from sqlmodel import Session, select

from app.auth.rbac import Role
from app.config import Config
from app.domain.audit_event_catalogue import describe_event
from app.domain.claim import (
    ApprovedClaimAmount,
    ExistingClaimSummary,
    calculate_available_funds,
)
from app.domain.claim import Claim as DomainClaim
from app.domain.pay_in_full import (
    PayInFullClaim,
    pay_in_full_claim_from_submitted_poa_claim,
)
from app.domain.payment_extract import poa_claim_payment_extract_lines
from app.domain.reference_rules import ReferenceRules
from app.models.application.enums import MeritsDecision, ProceedingId
from app.models.application.index import Application, Proceeding
from app.models.claim.enums import (
    ClaimDecisionStatus,
    ClaimStatus,
    ClaimType,
    InvoiceTypeCode,
    TaxCode,
)
from app.models.claim.index import (
    Claim,
    ClaimDecision,
    ClaimDecisionAmount,
    ClaimPaymentExtract,
)
from app.models.history.enums import ActorType, HistoryEventReference
from app.models.history.index import HistoryEvent
from bin import seed_dev as seed_dev_module
from tests.helpers.csv_helpers import parse_csv_rows

NOW = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
CONFTEST_APPLICATION_REFERENCE = "INQ-123-456"
NAMED_REFERENCES = ("INQ-YYY-YYY", "INQ-XXX-XXX")
# Deliberately recognisable fixed references that the app accepts but its generator
# would never emit (XXX is a banned word), so they are exempt from the generator rules.
PLACEHOLDER_REFERENCES = {
    "INQ-XXX-XXX",
    "INQ-YYY-YYY",
    "INQC-YYYY-YYYY",
    "INQC-XXXX-XXXX",
}
BULK_APPLICATION_COUNT = 2

APPLICATION_EVENTS = [
    HistoryEventReference.APPLICATION_SUBMITTED,
    HistoryEventReference.APPLICATION_SUBMISSION_CONFIRMATION,
    HistoryEventReference.APPLICATION_ASSESSMENT_COMPLETED,
    HistoryEventReference.CERTIFICATE_CREATED,
    HistoryEventReference.APPLICATION_GRANTED_EMAIL,
    HistoryEventReference.APPLICATION_GRANTED_LETTER,
]
AUTO_APPROVED_POA_EVENTS = [
    HistoryEventReference.CLAIM_SUBMITTED,
    HistoryEventReference.CLAIM_SUBMISSION_CONFIRMATION,
    HistoryEventReference.POA_AUTO_APPROVED,
    HistoryEventReference.CLAIM_APPROVED_EMAIL,
]
PENDING_CLAIM_EVENTS = [
    HistoryEventReference.CLAIM_SUBMITTED,
    HistoryEventReference.CLAIM_SUBMISSION_CONFIRMATION,
]
PAID_FINAL_BILL_EVENTS = [
    HistoryEventReference.CLAIM_SUBMITTED,
    HistoryEventReference.CLAIM_SUBMISSION_CONFIRMATION,
    HistoryEventReference.CLAIM_ASSESSMENT_COMPLETED,
    HistoryEventReference.CLAIM_FINAL_BILL_PAID_EMAIL,
]


@pytest.fixture
def seeded(session: Session) -> Session:
    session.add(
        Proceeding(
            proceeding_id=ProceedingId.IQPC,
            proceeding_name="Death in police custody",
            proceeding_description="Death in police custody",
        )
    )
    session.commit()
    random.seed(731)

    def session_factory():
        return nullcontext(session)

    with freeze_time(NOW):
        seed_dev_module.seed_dev(session_factory=session_factory)
        seed_dev_module.seed_bulk_applications(
            BULK_APPLICATION_COUNT, session_factory=session_factory
        )
    return session


def _applications(session: Session) -> list[Application]:
    return list(
        session.exec(
            select(Application)
            .where(Application.laa_reference != CONFTEST_APPLICATION_REFERENCE)
            .order_by(Application.application_id)
        ).all()
    )


def _application(session: Session, laa_reference: str) -> Application:
    return next(a for a in _applications(session) if a.laa_reference == laa_reference)


def _bulk_applications(session: Session) -> list[Application]:
    return [
        a for a in _applications(session) if a.laa_reference not in NAMED_REFERENCES
    ]


def _history(session: Session, application: Application) -> list[HistoryEvent]:
    return list(
        session.exec(
            select(HistoryEvent)
            .where(HistoryEvent.application_id == application.application_id)
            .order_by(HistoryEvent.timestamp, HistoryEvent.id)
        ).all()
    )


def _claims(session: Session, application: Application) -> list[Claim]:
    return list(
        session.exec(
            select(Claim)
            .where(Claim.application_id == application.application_id)
            .order_by(Claim.submission_date, Claim.claim_id)
        ).all()
    )


def _references(events: list[HistoryEvent]) -> list[HistoryEventReference]:
    return [event.event_reference for event in events]


def _domain_claim(claim: Claim) -> DomainClaim:
    template = claim.claim_cost_template
    return DomainClaim(
        claim_type=claim.claim_type_id,
        poa_type=claim.poa_type_id,
        net=claim.total_profit_cost_net,
        gross=claim.total_profit_cost_gross,
        vat_zero_total=claim.total_profit_cost_vat_zero,
        inquest_outcomes=tuple(
            outcome.inquest_outcome_id for outcome in claim.claim_inquest_outcomes
        ),
        cost_template_file_id=(
            template.claim_cost_template_file_id if template else None
        ),
        cost_template_file_name=(
            template.claim_cost_template_file_name if template else None
        ),
        has_counsel_been_paid=claim.has_counsel_been_paid,
        has_alternative_funding=claim.has_alternative_funding,
        has_recovery_costs_awarded=claim.has_recovery_costs_awarded,
        financial_recovery_previous_pre_certificate_costs=(
            claim.financial_recovery_previous_pre_certificate_costs
        ),
        financial_recovery_cost=claim.financial_recovery_cost,
        financial_recovery_damages=claim.financial_recovery_damages,
        financial_recovery_interest=claim.financial_recovery_interest,
        paying_party=claim.paying_party,
        number_of_counsel_instructed=claim.number_of_counsel_instructed,
    )


def _summary(claim: Claim) -> ExistingClaimSummary:
    return ExistingClaimSummary(
        claim_type=claim.claim_type_id,
        status=claim.status_id,
        poa_type=claim.poa_type_id,
        submission_date=claim.submission_date,
        net=claim.total_profit_cost_net,
        gross=claim.total_profit_cost_gross,
        vat_zero_total=claim.total_profit_cost_vat_zero,
    )


def _decision(session: Session, claim: Claim) -> ClaimDecision | None:
    return session.exec(
        select(ClaimDecision).where(ClaimDecision.claim_id == claim.claim_id)
    ).first()


def _extract_lines(session: Session, claim: Claim) -> list[ClaimPaymentExtract]:
    return list(
        session.exec(
            select(ClaimPaymentExtract)
            .where(ClaimPaymentExtract.claim_id == claim.claim_id)
            .order_by(ClaimPaymentExtract.sequence_number)
        ).all()
    )


def _extract_tuples(lines) -> list[tuple]:
    return [
        (
            line.sequence_number,
            line.invoice_number,
            line.invoice_amount,
            line.invoice_date,
            line.invoice_type,
            line.tax_code,
        )
        for line in lines
    ]


def _headers(role: Role) -> dict[str, str]:
    return {"Authorization": f"Bearer {role.value}"}


class TestSeededApplications:
    def test_seeds_the_named_applications_and_the_requested_bulk_applications(
        self, seeded
    ):
        references = [a.laa_reference for a in _applications(seeded)]

        assert references[:2] == list(NAMED_REFERENCES)
        assert len(references) == 2 + BULK_APPLICATION_COUNT

    def test_references_use_the_reference_formats_the_app_accepts(self, seeded):
        rules = ReferenceRules.from_file(Config.BANNED_WORDS_FILE_PATH)
        for application in _applications(seeded):
            references = [application.laa_reference] + [
                claim.claim_reference for claim in _claims(seeded, application)
            ]
            for reference in references:
                prefix, *parts = reference.split("-")
                assert (prefix, [len(p) for p in parts]) in (
                    ("INQ", [3, 3]),
                    ("INQC", [4, 4]),
                )
                if reference in PLACEHOLDER_REFERENCES:
                    continue
                assert all(c in rules.allowed_characters for c in "".join(parts))
                assert not rules.contains_banned_word("".join([prefix, *parts]))

    def test_granted_applications_record_the_cost_limitation_effective_date(
        self, seeded
    ):
        for application in _applications(seeded):
            proceeding = application.proceeding
            assert proceeding.merits_decision == MeritsDecision.GRANTED
            assert proceeding.certificate_start_date is not None
            assert (
                proceeding.substantive_cost_limitation_effective_date
                == proceeding.certificate_start_date
            )
            assert proceeding.certificate_issue_date <= NOW.date()

    def test_clients_have_no_placeholder_values(self, seeded):
        for application in _applications(seeded):
            client = application.client
            values = [
                client.client_first_name,
                client.client_last_name,
                client.correspondence_recipient_name,
                client.prev_application_reference,
                client.correspondence_address.address_line_2,
                client.correspondence_address.county,
                client.home_address.address_line_2,
                client.home_address.county,
            ]
            assert not {"string", "TBD", "Jones"} & {v for v in values if v}
            if not client.has_applied_previously:
                assert client.prev_application_reference is None

    def test_a_named_client_has_a_realistic_correspondence_recipient(self, seeded):
        client = _application(seeded, "INQ-YYY-YYY").client

        assert client.correspondence_recipient_name == "Robert Jones"

    def test_running_the_named_seed_again_changes_nothing(self, seeded):
        before = len(seeded.exec(select(HistoryEvent)).all())

        seed_dev_module.seed_dev(session_factory=lambda: nullcontext(seeded))

        assert len(seeded.exec(select(HistoryEvent)).all()) == before
        assert len(_applications(seeded)) == 2 + BULK_APPLICATION_COUNT


class TestSeededHistory:
    def test_pending_poa_application_has_the_history_its_state_implies(self, seeded):
        events = _history(seeded, _application(seeded, "INQ-YYY-YYY"))

        assert _references(events) == (
            APPLICATION_EVENTS + AUTO_APPROVED_POA_EVENTS + PENDING_CLAIM_EVENTS
        )

    def test_final_bill_application_has_the_history_its_state_implies(self, seeded):
        events = _history(seeded, _application(seeded, "INQ-XXX-XXX"))

        assert _references(events) == (
            APPLICATION_EVENTS
            + AUTO_APPROVED_POA_EVENTS
            + PENDING_CLAIM_EVENTS
            + PENDING_CLAIM_EVENTS
        )

    def test_bulk_applications_have_the_history_their_states_imply(self, seeded):
        expected = Counter(
            APPLICATION_EVENTS
            + 4 * AUTO_APPROVED_POA_EVENTS
            + PENDING_CLAIM_EVENTS
            + PAID_FINAL_BILL_EVENTS
        )

        for application in _bulk_applications(seeded):
            events = _history(seeded, application)
            assert Counter(_references(events)) == expected

    def test_application_events_record_what_the_services_record(self, seeded):
        application = _application(seeded, "INQ-YYY-YYY")
        provider_email = application.provider.email_address
        events = _history(seeded, application)[:6]
        data = {event.event_reference: event.event_data for event in events}

        assert data[HistoryEventReference.APPLICATION_SUBMITTED] is None
        assert data[HistoryEventReference.APPLICATION_SUBMISSION_CONFIRMATION] == {
            "recipient": provider_email,
            "channel": "email",
        }
        assert data[HistoryEventReference.APPLICATION_ASSESSMENT_COMPLETED] == {
            "merits_decision": "Granted"
        }
        assert data[HistoryEventReference.CERTIFICATE_CREATED] == {
            "laa_reference": "INQ-YYY-YYY"
        }
        assert data[HistoryEventReference.APPLICATION_GRANTED_EMAIL] == {
            "recipient": provider_email,
            "channel": "email",
        }
        letter = data[HistoryEventReference.APPLICATION_GRANTED_LETTER]
        assert letter["channel"] == "letter"
        assert set(letter["recipient"]) == {
            "address_line_1",
            "address_line_2",
            "town_or_city",
            "county",
            "postcode",
        }
        assert letter["recipient"]["address_line_1"].startswith("c/o Robert Jones ")

    def test_claim_events_record_what_the_services_record(self, seeded):
        application = _application(seeded, "INQ-YYY-YYY")
        provider_email = application.provider.email_address
        prior_poa, pending_poa = _claims(seeded, application)
        events = _history(seeded, application)[6:]

        assert [e.event_data for e in events] == [
            {
                "claim_type": "PAYMENT_ON_ACCOUNT",
                "claim_reference": prior_poa.claim_reference,
            },
            {"recipient": provider_email, "channel": "email"},
            {"claim_reference": prior_poa.claim_reference},
            {"claim_reference": prior_poa.claim_reference},
            {
                "claim_type": "PAYMENT_ON_ACCOUNT",
                "claim_reference": pending_poa.claim_reference,
            },
            {"recipient": provider_email, "channel": "email"},
        ]

    def test_paid_final_bill_events_record_the_decision_and_the_email(self, seeded):
        application = _bulk_applications(seeded)[0]
        final_bill = next(
            c
            for c in _claims(seeded, application)
            if c.claim_type_id == ClaimType.FINAL_BILL
        )
        events = _history(seeded, application)

        assessment = next(
            e
            for e in events
            if e.event_reference == HistoryEventReference.CLAIM_ASSESSMENT_COMPLETED
        )
        assert assessment.event_data == {
            "claim_type": "FINAL_BILL",
            "claim_reference": final_bill.claim_reference,
            "claim_decision": "PAY_IN_FULL",
            "profit_cost_net": "5000.00",
            "profit_cost_gross": "6000.00",
            "profit_cost_vat_zero": None,
            "disbursement_net": "5000.00",
            "disbursement_gross": "7000.00",
            "disbursement_vat_zero": "1000.00",
        }
        final_bill_email = events[-1]
        assert final_bill_email.event_reference == (
            HistoryEventReference.CLAIM_FINAL_BILL_PAID_EMAIL
        )
        assert final_bill_email.event_data == {
            "recipient": application.provider.email_address,
            "channel": "email",
        }

    def test_actors_match_who_would_have_performed_each_event(self, seeded):
        for application in _applications(seeded):
            claimants = {c.claimant_id for c in _claims(seeded, application)}
            for event in _history(seeded, application):
                if event.actor_type == ActorType.SYSTEM:
                    assert event.actor == "System"
                    assert event.actor_email_address is None
                    assert event.entra_user_object_id is None
                elif event.actor_type == ActorType.CASEWORKER:
                    assert event.actor == seed_dev_module.SEED_CASEWORKER_NAME
                    assert (
                        event.actor_email_address
                        == seed_dev_module.SEED_CASEWORKER_EMAIL
                    )
                    assert (
                        event.entra_user_object_id
                        == seed_dev_module.SEED_CASEWORKER_ENTRA_OBJECT_ID
                    )
                else:
                    assert event.actor in (
                        {application.provider.email_address} | claimants
                    )
                    assert event.actor_email_address == event.actor

    def test_events_follow_a_coherent_timeline(self, seeded):
        for application in _applications(seeded):
            events = _history(seeded, application)
            assert events[0].timestamp == application.created_at
            assert all(event.timestamp <= NOW for event in events)
            for claim in _claims(seeded, application):
                submitted = next(
                    e
                    for e in events
                    if e.event_reference == HistoryEventReference.CLAIM_SUBMITTED
                    and e.event_data["claim_reference"] == claim.claim_reference
                )
                assert submitted.timestamp == claim.submission_date
                assert claim.submission_date > application.created_at

    def test_every_event_can_be_described_for_the_audit_trail(self, seeded):
        for application in _applications(seeded):
            for event in _history(seeded, application):
                described = describe_event(
                    event.event_reference.value, event.event_data
                )
                assert described.title
                assert described.description


class TestSeededClaims:
    def test_every_claim_passes_the_domain_validation(self, seeded):
        for application in _applications(seeded):
            for claim in _claims(seeded, application):
                _domain_claim(claim).validate_total_claim_cost()

    def test_claim_statuses_are_ones_the_service_could_have_produced(self, seeded):
        for application in _applications(seeded):
            claims = _claims(seeded, application)
            for index, claim in enumerate(claims):
                if claim.claim_type_id != ClaimType.PAYMENT_ON_ACCOUNT:
                    assert claim.status_id in (
                        ClaimStatus.SUBMITTED,
                        ClaimStatus.PAY_IN_FULL,
                    )
                    continue
                domain_claim = _domain_claim(claim)
                earlier = [_summary(c) for c in claims[:index]]

                rejection = domain_claim.should_auto_reject(
                    application, earlier, claim.submission_date
                )
                needs_manual_review = domain_claim.requires_manual_review(
                    application, earlier
                )

                assert not rejection.is_rejected
                if needs_manual_review:
                    assert claim.status_id == ClaimStatus.SUBMITTED
                else:
                    assert domain_claim.is_eligible_for_auto_approval(application)
                    assert claim.status_id == ClaimStatus.PAY_IN_FULL

    def test_each_application_keeps_a_poa_claim_awaiting_assessment(self, seeded):
        for application in _applications(seeded):
            statuses = [
                c.status_id
                for c in _claims(seeded, application)
                if c.claim_type_id == ClaimType.PAYMENT_ON_ACCOUNT
            ]
            assert ClaimStatus.SUBMITTED in statuses
            assert ClaimStatus.PAY_IN_FULL in statuses

    def test_funds_remaining_is_what_the_service_calculates_at_submission(self, seeded):
        for application in _applications(seeded):
            limit = application.proceeding.substantive_cost_limitation
            approved: list[ApprovedClaimAmount] = []
            for claim in _claims(seeded, application):
                funds_before = calculate_available_funds(limit, approved)
                payment = ApprovedClaimAmount(
                    None,
                    claim.total_profit_cost_gross,
                    claim.total_profit_cost_vat_zero,
                ).payment_amount
                assert claim.total_funds_remaining_after_claim == (
                    funds_before - payment
                ).quantize(Decimal("0.01"))
                if claim.status_id == ClaimStatus.PAY_IN_FULL:
                    approved.append(
                        ApprovedClaimAmount(
                            ClaimDecisionStatus.PAY_IN_FULL,
                            claim.total_profit_cost_gross,
                            claim.total_profit_cost_vat_zero,
                        )
                    )

    def test_decisions_exist_only_for_assessed_claims_and_are_valid(self, seeded):
        for application in _applications(seeded):
            for claim in _claims(seeded, application):
                decision = _decision(seeded, claim)
                if claim.status_id == ClaimStatus.SUBMITTED:
                    assert decision is None
                    continue
                assert decision.decision == ClaimDecisionStatus.PAY_IN_FULL
                assert claim.submission_date <= decision.created_at <= NOW
                amount = seeded.exec(
                    select(ClaimDecisionAmount).where(
                        ClaimDecisionAmount.claim_decision_id
                        == decision.claim_decision_id
                    )
                ).one()
                paid = PayInFullClaim(
                    claim_type_id=claim.claim_type_id,
                    poa_type_id=claim.poa_type_id,
                    profit_cost_net=amount.profit_cost_net,
                    profit_cost_gross=amount.profit_cost_gross,
                    profit_cost_vat_zero=amount.profit_cost_vat_zero,
                    disbursement_net=amount.disbursement_net,
                    disbursement_gross=amount.disbursement_gross,
                    disbursement_vat_zero=amount.disbursement_vat_zero,
                )
                paid.validate()
                if claim.claim_type_id == ClaimType.PAYMENT_ON_ACCOUNT:
                    assert paid == pay_in_full_claim_from_submitted_poa_claim(claim)

    def test_poa_payment_extract_lines_are_what_the_service_creates(self, seeded):
        for application in _applications(seeded):
            for claim in _claims(seeded, application):
                if claim.claim_type_id != ClaimType.PAYMENT_ON_ACCOUNT:
                    continue
                lines = _extract_lines(seeded, claim)
                if claim.status_id == ClaimStatus.SUBMITTED:
                    assert lines == []
                    continue
                expected = poa_claim_payment_extract_lines(
                    claim, pay_in_full_claim_from_submitted_poa_claim(claim)
                )
                assert _extract_tuples(lines) == _extract_tuples(expected)
                assert all(
                    claim.submission_date <= line.created_at <= NOW for line in lines
                )

    def test_paid_final_bill_extract_pays_the_decision_and_recoups_paid_poas(
        self, seeded
    ):
        for application in _bulk_applications(seeded):
            claims = _claims(seeded, application)
            final_bill = next(
                c for c in claims if c.claim_type_id == ClaimType.FINAL_BILL
            )
            recouped = [
                line
                for poa in claims
                if poa.claim_type_id == ClaimType.PAYMENT_ON_ACCOUNT
                and poa.status_id == ClaimStatus.PAY_IN_FULL
                for line in _extract_lines(seeded, poa)
            ]
            decision_date = _decision(seeded, final_bill).created_at.date()
            invoice_date = final_bill.submission_date.date()
            reference = final_bill.claim_reference

            lines = _extract_tuples(_extract_lines(seeded, final_bill))

            fees = InvoiceTypeCode.FINAL_BILL_FEES
            disbursement = InvoiceTypeCode.FINAL_BILL_DISBURSEMENT
            assert lines == [
                (
                    1,
                    f"{reference}_001",
                    Decimal("6000.00"),
                    invoice_date,
                    fees,
                    TaxCode.GB_VAT_20,
                ),
                (
                    2,
                    f"{reference}_002",
                    Decimal("6000.00"),
                    invoice_date,
                    disbursement,
                    TaxCode.GB_VAT_20,
                ),
                (
                    3,
                    f"{reference}_003",
                    Decimal("1000.00"),
                    invoice_date,
                    disbursement,
                    TaxCode.ZERO_VAT,
                ),
            ] + [
                (
                    3 + position,
                    f"{original.invoice_number}-R",
                    -original.invoice_amount,
                    decision_date,
                    InvoiceTypeCode.RECOUPED,
                    original.tax_code,
                )
                for position, original in enumerate(recouped, start=1)
            ]


class TestSeededDataThroughTheApi:
    def test_history_endpoint_returns_each_applications_events_newest_first(
        self, seeded, client
    ):
        for application in _applications(seeded):
            response = client.get(
                f"/applications/{application.laa_reference}/history",
                headers=_headers(Role.APPLICATIONS_CASEWORKER),
            )

            assert response.status_code == 200
            returned = response.json()
            assert sorted(e["eventReference"] for e in returned) == sorted(
                e.event_reference.value for e in _history(seeded, application)
            )
            timestamps = [e["timestamp"] for e in returned]
            assert timestamps == sorted(timestamps, reverse=True)

    def test_certificate_is_complete_and_free_of_placeholders(self, seeded, client):
        for application in _applications(seeded):
            response = client.get(
                f"/applications/{application.laa_reference}/certificate",
                headers=_headers(Role.APPLICATIONS_CASEWORKER),
            )

            assert response.status_code == 200
            certificate = response.json()
            assert (
                certificate["costLimitationEffectiveDate"]
                == application.proceeding.certificate_start_date.isoformat()
            )
            assert "string" not in str(certificate["clientAddress"])

    def test_audit_trail_extract_reports_every_seeded_event(self, seeded, client):
        expected = sum(len(_history(seeded, a)) for a in _applications(seeded))

        response = client.get(
            "/reports/audit-trail",
            params={
                "from": (NOW - timedelta(days=5)).date().isoformat(),
                "to": NOW.date().isoformat(),
            },
            headers=_headers(Role.ASSURANCE),
        )

        assert response.status_code == 200
        rows = parse_csv_rows(response.text)
        history_rows = [
            r for r in rows if not r["Event reference"].startswith("EVT-AUD")
        ]
        assert len(history_rows) == expected
        assert any(row["Firm name"] for row in history_rows)
