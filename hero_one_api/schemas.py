from ninja import Schema
from typing import Optional

# Common Schemas
class ErrorResponseSchema(Schema):
    success: bool = False
    message: str

# Registration Schemas
class RegistrationRequestSchema(Schema):
    full_name: str
    email: str
    password: str
    phone_number: Optional[str] = None

class RegistrationResponseSchema(Schema):
    success: bool
    message: str

# Registration Verification Schemas
class RegistrationVerificationRequestSchema(Schema):
    email: str
    otp_code: str

# Signin Schemas
class SigninRequestSchema(Schema):
    email: str
    password: str

class SigninResponseSchema(Schema):
    success: bool
    message: str

# Signin Verification Schemas
class SigninVerificationRequestSchema(Schema):
    email: str
    otp_code: str

# OTP Response Schemas
class TokenResponseSchema(Schema):
    success: bool
    message: str
    access_token: str
    refresh_token: str

# Request OTP Manual Schema ( Resend OTP / Manually trigger a otp)
class OTPRequestSchema(Schema):
    email: str
    otp_type: str = "registration"  # registration, signin, password_reset

class OTPRequestResponseSchema(Schema):
    success: bool
    message: str

# Password Reset Schema
class PasswordResetRequestSchema(Schema):
    email: str

class PasswordResetVerificationSchema(Schema):
    email: str
    otp_code: str
    new_password: str

class PasswordResetResponseSchema(Schema):
    success: bool
    message: str

# OAuth Signin Schema
class OAuthSigninRequestSchema(Schema):
    provider: str
    email: str
    full_name: str
    image: Optional[str] = None
    oauth_id: str
    access_token: str

class OAuthSigninResponseSchema(Schema):
    success: bool
    access_token: str
    refresh_token: str


