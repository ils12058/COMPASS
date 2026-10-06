"""Referral domain errors shared by services and explicit content adapters."""


class ReferralError(RuntimeError):
    pass


class InvalidReferralInput(ReferralError):
    pass
