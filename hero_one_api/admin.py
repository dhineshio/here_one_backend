from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta
from .models import User, OTPVerification

# Register your models here.
class HeroOneAdmin(admin.AdminSite):
    site_header = "HeroOne Authentication Admin"
    site_title = "HeroOne Admin"
    index_title = "Authentication Management Dashboard"
    
    def index(self, request, extra_context=None):
        """Custom admin dashboard with statistics"""
        extra_context = extra_context or {}
        
        # User statistics
        total_users = User.objects.count()
        verified_users = User.objects.filter(is_verified=True).count()
        unverified_users = User.objects.filter(is_verified=False).count()
        
        # OTP statistics
        total_otps = OTPVerification.objects.count()
        active_otps = OTPVerification.objects.filter(is_active=True, is_used=False).count()
        expired_otps = OTPVerification.objects.filter(expires_at__lt=timezone.now()).count()
        
        # Recent registrations (last 24 hours)
        yesterday = timezone.now() - timedelta(days=1)
        recent_registrations = User.objects.filter(date_joined__gte=yesterday).count()
        
        # Users needing attention (unverified for more than 24 hours)
        old_unverified = User.objects.filter(
            is_verified=False,
            date_joined__lt=yesterday
        ).count()
        
        extra_context.update({
            'dashboard_stats': {
                'total_users': total_users,
                'verified_users': verified_users,
                'unverified_users': unverified_users,
                'verification_rate': round((verified_users / total_users * 100) if total_users > 0 else 0, 1),
                'freelancers': freelancers,
                'startups': startups,
                'total_otps': total_otps,
                'active_otps': active_otps,
                'expired_otps': expired_otps,
                'recent_registrations': recent_registrations,
                'old_unverified': old_unverified,
            }
        })
        
        return super().index(request, extra_context)

    
admin_site = HeroOneAdmin(name='admin')


@admin.register(User, site=admin_site)
class UserAdmin(BaseUserAdmin):
    """Custom User Admin"""
    
    # Fields to display in the user list
    list_display = (
        'email', 
        'username', 
        'full_name', 
        'phone_number',
        'oauth_provider',
        'is_verified',
        'verification_status_display',
        'is_active', 
        'is_staff', 
        'date_joined',
        'pending_otps_count'
    )
    
    # Fields to filter by
    list_filter = (
        'is_verified',
        'oauth_provider',
        'is_staff', 
        'is_superuser', 
        'is_active', 
        'date_joined'
    )
    
    # Fields to search by
    search_fields = ('email', 'username', 'full_name', 'phone_number')
    
    # Default ordering
    ordering = ('email',)
    
    # Fields that should be read-only
    readonly_fields = ('date_joined', 'last_login', 'username')
    
    # Fieldsets for the user detail/edit page
    fieldsets = (
        (None, {
            'fields': ('email', 'password')
        }),
        (_('Personal info'), {
            'fields': (
                'full_name', 
                'phone_number',
                'username',
                'profile_pic'
            )
        }),
        (_('OAuth Information'), {
            'fields': (
                'oauth_provider',
                'oauth_id',
                'oauth_access_token'
            ),
            'classes': ('collapse',),  # Make it collapsible
        }),
        (_('Verification & Permissions'), {
            'fields': (
                'is_verified',
                'is_active', 
                'is_staff', 
                'is_superuser',
                'groups', 
                'user_permissions'
            ),
        }),
        (_('Important dates'), {
            'fields': ('last_login', 'date_joined')
        }),
    )
    
    # Fieldsets for adding a new user
    add_fieldsets = (
        (_('Authentication'), {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
        (_('Personal Information'), {
            'classes': ('wide',),
            'fields': ('full_name', 'phone_number'),
        }),
    )
    
    # Use email as the username field
    username_field = 'email'
    
    def get_form(self, request, obj=None, **kwargs):
        """
        Override to add custom validation and help text
        """
        form = super().get_form(request, obj, **kwargs)
        
        # Add help text for team_members_count field
        if 'team_members_count' in form.base_fields:
            form.base_fields['team_members_count'].help_text = (
                "Required for startup users. Leave empty for freelancers."
            )
        
        # Add help text for phone_number field
        if 'phone_number' in form.base_fields:
            form.base_fields['phone_number'].help_text = (
                "Optional phone number for contact purposes."
            )
        
        return form
    
    def verification_status_display(self, obj):
        """Display verification status with color coding"""
        if obj.is_verified:
            return "✅ Verified"
        else:
            return "❌ Unverified"
    verification_status_display.short_description = 'Status'
    verification_status_display.admin_order_field = 'is_verified'
    
    def pending_otps_count(self, obj):
        """Count of active OTPs for this user"""
        count = obj.otp_verifications.filter(is_active=True, is_used=False).count()
        if count > 0:
            return f"📧 {count}"
        return "—"
    pending_otps_count.short_description = 'Pending OTPs'
    
    def get_queryset(self, request):
        """Optimize queryset with prefetch_related for OTPs"""
        return super().get_queryset(request).prefetch_related('otp_verifications')
    
    # Admin Actions
    actions = ['mark_as_verified', 'mark_as_unverified', 'cleanup_user_otps', 'delete_unverified_users']
    
    def mark_as_verified(self, request, queryset):
        """Mark selected users as verified"""
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} user(s) marked as verified.')
    mark_as_verified.short_description = "Mark selected users as verified"
    
    def mark_as_unverified(self, request, queryset):
        """Mark selected users as unverified"""
        updated = queryset.update(is_verified=False)
        self.message_user(request, f'{updated} user(s) marked as unverified.')
    mark_as_unverified.short_description = "Mark selected users as unverified"
    
    def cleanup_user_otps(self, request, queryset):
        """Clean up all OTPs for selected users"""
        total_deleted = 0
        for user in queryset:
            deleted_count = user.otp_verifications.all().count()
            user.otp_verifications.all().delete()
            total_deleted += deleted_count
        self.message_user(request, f'Cleaned up {total_deleted} OTP(s) for {queryset.count()} user(s).')
    cleanup_user_otps.short_description = "Clean up OTPs for selected users"
    
    def delete_unverified_users(self, request, queryset):
        """Delete unverified users from selection"""
        unverified_users = queryset.filter(is_verified=False)
        count = unverified_users.count()
        
        if count > 0:
            # Clean up their OTPs first
            for user in unverified_users:
                user.otp_verifications.all().delete()
            unverified_users.delete()
            self.message_user(request, f'Deleted {count} unverified user(s) and their OTPs.')
        else:
            self.message_user(request, 'No unverified users found in selection.')
    delete_unverified_users.short_description = "Delete unverified users (and their OTPs)"
    
    def save_model(self, request, obj, form, change):
        """
        Override to handle custom validation
        """
        super().save_model(request, obj, form, change)


@admin.register(OTPVerification, site=admin_site)
class OTPVerificationAdmin(admin.ModelAdmin):
    """Admin interface for OTP Verification"""
    
    # Fields to display in the list
    list_display = (
        'user_email',
        'user_verification_status',
        'otp_code',
        'otp_type',
        'created_at',
        'time_remaining',
        'is_used',
        'is_active',
        'status_display'
    )
    
    # Fields to filter by
    list_filter = (
        'otp_type',
        'is_used',
        'is_active',
        'created_at',
        'expires_at'
    )
    
    # Fields to search by
    search_fields = ('user__email', 'user__full_name', 'otp_code')
    
    # Default ordering (newest first)
    ordering = ('-created_at',)
    
    # Read-only fields
    readonly_fields = ('created_at', 'expires_at', 'time_remaining', 'status_display')
    
    # Fields for the detail/edit page
    fields = (
        'user',
        'otp_code',
        'otp_type',
        'created_at',
        'expires_at',
        'time_remaining',
        'is_used',
        'is_active',
        'status_display'
    )
    
    def user_email(self, obj):
        """Display user email in the list"""
        return obj.user.email
    user_email.short_description = 'User Email'
    user_email.admin_order_field = 'user__email'
    
    def user_verification_status(self, obj):
        """Display user verification status"""
        if obj.user.is_verified:
            return "✅ Verified"
        else:
            return "❌ Unverified"
    user_verification_status.short_description = 'User Status'
    user_verification_status.admin_order_field = 'user__is_verified'
    
    def time_remaining(self, obj):
        """Display time remaining for OTP"""
        now = timezone.now()
        if obj.expires_at > now:
            delta = obj.expires_at - now
            minutes = int(delta.total_seconds() / 60)
            seconds = int(delta.total_seconds() % 60)
            return f"{minutes}m {seconds}s"
        else:
            return "⏰ Expired"
    time_remaining.short_description = 'Time Left'
    
    def status_display(self, obj):
        """Comprehensive status display"""
        if obj.is_used:
            return "✅ Used"
        elif timezone.now() > obj.expires_at:
            return "⏰ Expired"
        elif obj.is_active:
            return "🟢 Active"
        else:
            return "🔴 Inactive"
    status_display.short_description = 'Status'
    
    # Admin Actions
    actions = ['cleanup_expired_otps', 'deactivate_otps', 'delete_used_otps']
    
    def cleanup_expired_otps(self, request, queryset):
        """Clean up expired OTPs"""
        expired_otps = queryset.filter(expires_at__lt=timezone.now())
        count = expired_otps.count()
        expired_otps.delete()
        self.message_user(request, f'Cleaned up {count} expired OTP(s).')
    cleanup_expired_otps.short_description = "Delete expired OTPs"
    
    def deactivate_otps(self, request, queryset):
        """Deactivate selected OTPs"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'Deactivated {updated} OTP(s).')
    deactivate_otps.short_description = "Deactivate selected OTPs"
    
    def delete_used_otps(self, request, queryset):
        """Delete used OTPs"""
        used_otps = queryset.filter(is_used=True)
        count = used_otps.count()
        used_otps.delete()
        self.message_user(request, f'Deleted {count} used OTP(s).')
    delete_used_otps.short_description = "Delete used OTPs"
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('user')
    
    def has_add_permission(self, request):
        """Disable adding OTPs through admin (should be generated programmatically)"""
        return False


# Also register with default admin for backward compatibility
@admin.register(User)
class DefaultUserAdmin(UserAdmin):
    """Default admin registration for User"""
    pass


@admin.register(OTPVerification)
class DefaultOTPVerificationAdmin(OTPVerificationAdmin):
    """Default admin registration for OTPVerification"""
    pass
