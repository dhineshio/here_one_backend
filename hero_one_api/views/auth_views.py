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
    OAuthSigninRequestSchema,
    OAuthSigninResponseSchema,
)
from ..models import OTPVerification

User = get_user_model()

# Initialize Django Ninja API for authentication
auth_api = NinjaAPI(version="1.0.0", title="Authentication API", urls_namespace="auth")

@auth_api.post("/register", response={201: RegistrationResponseSchema, 400: ErrorResponseSchema})
def register_user(request, data: RegistrationRequestSchema):
    try:   
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
                full_name=data.full_name,
                phone_number=data.phone_number,
                is_verified=False
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

@auth_api.post("/oauth-signin", response={200: OAuthSigninResponseSchema, 400: ErrorResponseSchema})
def oauth_signin(request, data: OAuthSigninRequestSchema):
    """
    OAuth signin endpoint that handles authentication via OAuth providers (Google, Facebook, etc.)
    
    Logic:
    1. Check if user exists by email or oauth_id
    2. If new user, create account with OAuth details
    3. If existing user, update last login and OAuth info
    4. Generate and return JWT tokens
    """
    try:
        user = None
        
        # Try to find user by oauth_id first (most reliable for OAuth users)
        if data.oauth_id:
            try:
                user = User.objects.get(oauth_id=data.oauth_id)
            except User.DoesNotExist:
                pass
        
        # If not found by oauth_id, try by email
        if not user and data.email:
            try:
                user = User.objects.get(email=data.email)
            except User.DoesNotExist:
                pass
        
        # Create new user if doesn't exist
        if not user:
            with transaction.atomic():
                # Generate a random password for OAuth users (they won't use it)
                import secrets
                random_password = secrets.token_urlsafe(32)
                
                user = User.objects.create_user(
                    email=data.email,
                    password=random_password,
                    full_name=data.full_name,
                    oauth_provider=data.provider,
                    oauth_id=data.oauth_id,
                    oauth_access_token=data.access_token,
                    is_verified=True,  # OAuth users are automatically verified
                )
                
                # Update profile picture if provided
                if data.image:
                    # Note: In production, you might want to download and save the image
                    # For now, we'll just store the URL in a custom field or skip it
                    pass
        else:
            # Update existing user's OAuth info and last login
            user.oauth_provider = data.provider
            user.oauth_id = data.oauth_id
            user.oauth_access_token = data.access_token
            user.last_login = timezone.now()
            
            # If user wasn't verified before, mark as verified (OAuth verification)
            if not user.is_verified:
                user.is_verified = True
            
            # Update full name if it changed
            if data.full_name and data.full_name != user.full_name:
                user.full_name = data.full_name
            
            user.save(update_fields=['oauth_provider', 'oauth_id', 'oauth_access_token', 
                                     'last_login', 'is_verified', 'full_name'])
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        
        return 200, {
            "success": True,
            "access_token": access_token,
            "refresh_token": refresh_token
        }
        
    except Exception as e:
        return 400, {
            "success": False,
            "message": f"OAuth signin failed: {str(e)}"
        }