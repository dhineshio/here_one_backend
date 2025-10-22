from ninja import NinjaAPI
from django.contrib.auth import get_user_model, authenticate
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
from ..schemas import (
    RegistrationRequestSchema,
    RegistrationResponseSchema,
    ErrorResponseSchema,
    SigninRequestSchema,
    SigninResponseSchema,
    OTPRequestSchema,
    OTPRequestResponseSchema,
    RegistrationVerificationRequestSchema,
    SigninVerificationRequestSchema,
    PasswordResetRequestSchema,
    PasswordResetVerificationSchema,
    TokenResponseSchema,
    PasswordResetResponseSchema,
)
from ..models import OTPVerification

User = get_user_model()

# Initialize Django Ninja API for authentication
auth_api = NinjaAPI(version="1.0.0", title="Authentication API", urls_namespace="auth")

@auth_api.post("/register", response={201: RegistrationResponseSchema, 400: ErrorResponseSchema})
def register_user(request, data: RegistrationRequestSchema):
    try:
        # Validate user_type
        if data.user_type not in ['freelancer', 'startup']:
            return 400, {
                "success": False,
                "message": "Invalid user type. Must be either 'freelancer' or 'startup'"
            }
        
        # Validate team_members_count for startups
        if data.user_type == 'startup' and data.team_members_count is None:
            return 400, {
                "success": False,
                "message": "Team members count is required for startup users"
            }
        
        # Check if verified user already exists
        existing_verified_user = User.objects.filter(email=data.email, is_verified=True).first()
        if existing_verified_user:
            return 400, {
                "success": False,
                "message": "A verified user with this email already exists. Please sign in instead."
            }
        
        # Handle unverified user - delete and allow re-registration
        existing_unverified_user = User.objects.filter(email=data.email, is_verified=False).first()
        if existing_unverified_user:
            # Clean up unverified user and their OTPs
            OTPVerification.objects.filter(user=existing_unverified_user).delete()
            existing_unverified_user.delete()
        
        # Create user within a transaction
        with transaction.atomic():
            user = User.objects.create_user(
                email=data.email,
                password=data.password,
                first_name=data.first_name,
                last_name=data.last_name,
                phone_number=data.phone_number,
                user_type=data.user_type,
                team_members_count=data.team_members_count if data.user_type == 'startup' else None,
                is_verified=False  # Explicitly set as unverified
            )
            
            # Generate OTP for registration
            otp = OTPVerification.generate_otp(user, otp_type='registration')
        
        # Return success response with OTP notification
        return 201, {
            "success": True,
            "message": f"OTP sent to {user.email}. Please verify OTP to complete registration."
        }
        
    except ValidationError as e:
        error_msg = str(e)
        if hasattr(e, 'message_dict'):
            # Extract first error message from validation errors
            error_msg = next(iter(e.message_dict.values()))[0] if e.message_dict else str(e)
        return 400, {
            "success": False,
            "message": f"Validation error: {error_msg}"
        }
    
    except Exception as e:
        return 400, {
            "success": False,
            "message": f"Registration failed: {str(e)}"
        }

@auth_api.post("/verify-registration", response={200: TokenResponseSchema, 400: ErrorResponseSchema})
def verify_registration_otp(request, data: RegistrationVerificationRequestSchema):
    try:
        # Check if user exists
        try:
            user = User.objects.get(email=data.email)
        except User.DoesNotExist:
            return 400, {
                "success": False,
                "message": "User with this email does not exist"
            }
        
        # Verify OTP for registration
        is_valid, message = OTPVerification.verify_otp(user, data.otp_code, 'registration')
        
        if not is_valid:
            return 400, {
                "success": False,
                "message": message
            }
        
        # Registration OTP verified successfully - complete registration
        # Mark user as verified
        user.is_verified = True
        user.last_login = timezone.now()
        user.save(update_fields=['is_verified', 'last_login'])
        
        # Generate JWT tokens for the newly registered user
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        
        return 200, {
            "success": True,
            "message": "Registration completed successfully. You are now signed in.",
            "access_token": access_token,
            "refresh_token": refresh_token,
        }
        
    except Exception as e:
        return 400, {
            "success": False,
            "message": f"Registration verification failed: {str(e)}"
        }

@auth_api.post("/signin", response={200: SigninResponseSchema, 400: ErrorResponseSchema})
def signin_user(request, data: SigninRequestSchema):
    try:
        # Check if user exists first
        try:
            user_check = User.objects.get(email=data.email)
            if not user_check.is_verified:
                return 400, {
                    "success": False,
                    "message": "Account not verified. Please complete registration first or register again."
                }
        except User.DoesNotExist:
            return 400, {
                "success": False,
                "message": "Invalid email or password"
            }
        
        # Authenticate user
        user = authenticate(request, email=data.email, password=data.password)
        
        if user is None:
            return 400, {
                "success": False,
                "message": "Invalid email or password"
            }
        
        if not user.is_active:
            return 400, {
                "success": False,
                "message": "User account is deactivated"
            }
        
        if not user.is_verified:
            return 400, {
                "success": False,
                "message": "Account not verified. Please complete registration first."
            }
        
        # Generate OTP for signin (every login requires OTP)
        otp = OTPVerification.generate_otp(user, otp_type='signin')

        return 200, {
            "success": True,
            "message": f"OTP sent to {user.email}. Please verify OTP to complete signin."
        }
        
    except Exception as e:
        return 400, {
            "success": False,
            "message": f"Signin failed: {str(e)}"
        }

@auth_api.post("/verify-signin", response={200: TokenResponseSchema, 400: ErrorResponseSchema})
def verify_signin_otp(request, data: SigninVerificationRequestSchema):
    try:
        # Check if user exists
        try:
            user = User.objects.get(email=data.email)
        except User.DoesNotExist:
            return 400, {
                "success": False,
                "message": "User with this email does not exist"
            }
        
        # Check if user is active
        if not user.is_active:
            return 400, {
                "success": False,
                "message": "User account is deactivated"
            }
        
        # Check if user is verified
        if not user.is_verified:
            return 400, {
                "success": False,
                "message": "Account not verified. Please complete registration first."
            }
        
        # Verify OTP for sign-in
        is_valid, message = OTPVerification.verify_otp(user, data.otp_code, 'signin')
        
        if not is_valid:
            return 400, {
                "success": False,
                "message": message
            }
        
        # Sign-in OTP verified successfully
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        
        # Update last login
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        return 200, {
            "success": True,
            "message": "Sign-in successful. Welcome back!",
            "access_token": access_token,
            "refresh_token": refresh_token
        }
        
    except Exception as e:
        return 400, {
            "success": False,
            "message": f"Sign-in verification failed: {str(e)}"
        }

@auth_api.post("/request-otp", response={200: OTPRequestResponseSchema, 400: OTPRequestResponseSchema})
def request_otp(request, data: OTPRequestSchema):
    try:
        # Check if user exists
        try:
            user = User.objects.get(email=data.email)
        except User.DoesNotExist:
            return 400, {
                "success": False,
                "message": "User with this email does not exist",
            }
        
        # Validate OTP type
        if data.otp_type not in ['registration', 'signin', 'password_reset']:
            return 400, {
                "success": False,
                "message": "Invalid OTP type. Must be 'registration', 'signin', or 'password_reset'",
            }
        
        # Check verification status based on OTP type
        if data.otp_type == 'registration':
            if user.is_verified:
                return 400, {
                    "success": False,
                    "message": "User is already verified. Please sign in instead.",
                }
        else:  # signin or password_reset
            if not user.is_verified:
                return 400, {
                    "success": False,
                    "message": "Account not verified. Please complete registration first.",
                }
        
        # Generate OTP
        otp = OTPVerification.generate_otp(user, otp_type=data.otp_type)
        
        # TODO: Send OTP via email service
        # For now, just return success (in production, integrate with email service)
        
        return 200, {
            "success": True,
            "message": f"OTP sent to {data.email}. Please check your email.",
        }
        
    except Exception as e:
        return 400, {
            "success": False,
            "message": f"Failed to send OTP: {str(e)}",
        }

@auth_api.post("/request-password-reset", response={200: PasswordResetResponseSchema, 400: ErrorResponseSchema})
def request_password_reset(request, data: PasswordResetRequestSchema):
    try:
        # Check if user exists
        try:
            user = User.objects.get(email=data.email)
        except User.DoesNotExist:
            return 400, {
                "success": False,
                "message": "User with this email does not exist"
            }
        
        # Check if user is active
        if not user.is_active:
            return 400, {
                "success": False,
                "message": "User account is deactivated"
            }
        
        # Check if user is verified
        if not user.is_verified:
            return 400, {
                "success": False,
                "message": "Account not verified. Please complete registration first."
            }
        
        # Generate OTP for password reset
        otp = OTPVerification.generate_otp(user, otp_type='password_reset')
        
        # TODO: Send OTP via email service
        # For now, just return success (in production, integrate with email service)
        
        return 200, {
            "success": True,
            "message": f"Password reset OTP sent to {user.email}. Please check your email."
        }
        
    except Exception as e:
        return 400, {
            "success": False,
            "message": f"Failed to send password reset OTP: {str(e)}"
        }

@auth_api.post("/verify-password-reset", response={200: PasswordResetResponseSchema, 400: ErrorResponseSchema})
def verify_password_reset_otp(request, data: PasswordResetVerificationSchema):
    try:
        # Check if user exists
        try:
            user = User.objects.get(email=data.email)
        except User.DoesNotExist:
            return 400, {
                "success": False,
                "message": "User with this email does not exist"
            }
        
        # Check if user is verified
        if not user.is_verified:
            return 400, {
                "success": False,
                "message": "Account not verified. Please complete registration first."
            }
        
        # Verify OTP for password reset
        is_valid, message = OTPVerification.verify_otp(user, data.otp_code, 'password_reset')
        
        if not is_valid:
            return 400, {
                "success": False,
                "message": message
            }
        
        # OTP verified successfully - update password
        user.set_password(data.new_password)
        user.save(update_fields=['password'])
        
        return 200, {
            "success": True,
            "message": "Password reset successful. You can now sign in with your new password."
        }
        
    except Exception as e:
        return 400, {
            "success": False,
            "message": f"Password reset verification failed: {str(e)}"
        }