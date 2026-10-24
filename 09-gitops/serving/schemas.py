from pydantic import BaseModel


class UserData(BaseModel):
    session_dt: str
    conversion_dt: str | None = None
    register_date: str

    campaign_id: int
    page: str
    sub1: int | str | None = None
    sub2: str | None = None
    sub3: int | str | None = None

    device_type: str | None = None
    auto_city: str | None = None
    auto_country: str | None = None
    auto_state: str | None = None

    business_type: str | None = None
    credit_score: str | None = None
    industry: str | None = None
    loan_amount: str | None = None
    loan_reason: str | None = None
    monthly_revenue: str | None = None
    time_in_business: str | None = None

    fname: str | None = None
    lname: str | None = None
    cellphone: int
