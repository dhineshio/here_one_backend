from ninja import Router
from ninja.security import HttpBearer
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model
from ..models.client_models import Client
from ..schemas import (
    ErrorResponseSchema,
    ClientResponseSchema,
    ClientListResponseSchema
)

User = get_user_model()

# JWT Authentication
class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        try:
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            user = User.objects.get(id=user_id)
            return user
        except Exception:
            return None

client_router = Router(tags=["Clients"])


@client_router.get(
    "/my-clients",
    response={200: ClientListResponseSchema, 401: ErrorResponseSchema},
    auth=AuthBearer(),
    summary="Get list of clients for logged-in user",
    description="Returns all clients associated with the authenticated user"
)
def get_user_clients(request):
    """
    Get all clients for the authenticated user
    
    Returns:
        - List of clients with their details
        - Total count of clients
    """
    user = request.auth
    
    if not user:
        return 401, {
            "success": False,
            "message": "Authentication required",
        }
    
    # Get all clients for the user
    clients = Client.objects.filter(user=user).order_by('-created_at')
    
    # Serialize clients
    client_data = [
        {
            "id": client.id,
            "client_name": client.client_name,
            "contact_person": client.contact_person,
            "contact_email": client.contact_email,
            "contact_phone": client.contact_phone,
            "industry_type": client.industry_type,
            "brand_logo": client.brand_logo.url if client.brand_logo else None,
            "facebook_url": client.facebook_url,
            "instagram_url": client.instagram_url,
            "youtube_url": client.youtube_url,
            "linkedin_url": client.linkedin_url,
            "twitter_url": client.twitter_url,
            "tiktok_url": client.tiktok_url,
            "preferred_post_time": client.preferred_post_time.strftime('%H:%M') if client.preferred_post_time else None,
            "created_at": client.created_at,
            "updated_at": client.updated_at,
        }
        for client in clients
    ]
    
    return 200, {
        "success": True,
        "message": "Clients retrieved successfully",
        "data": client_data,
        "count": len(client_data)
    }


@client_router.get(
    "/my-clients/{client_id}",
    response={200: ClientResponseSchema, 401: ErrorResponseSchema, 404: ErrorResponseSchema},
    auth=AuthBearer(),
    summary="Get specific client details",
    description="Returns details of a specific client by ID for the authenticated user"
)
def get_client_detail(request, client_id: int):
    """
    Get details of a specific client
    
    Args:
        client_id: The ID of the client to retrieve
    
    Returns:
        - Client details if found and belongs to user
        - 404 if not found or doesn't belong to user
    """
    user = request.auth
    
    if not user:
        return 401, {
            "success": False,
            "message": "Invalid or missing authentication token",
        }
    
    # Get client and verify ownership
    try:
        client = Client.objects.get(id=client_id, user=user)
    except Client.DoesNotExist:
        return 404, {
            "success": False,
            "message": f"No client found with ID {client_id} for this user",
        }
    
    return 200, {
        "id": client.id,
        "client_name": client.client_name,
        "contact_person": client.contact_person,
        "contact_email": client.contact_email,
        "contact_phone": client.contact_phone,
        "industry_type": client.industry_type,
        "brand_logo": client.brand_logo.url if client.brand_logo else None,
        "facebook_url": client.facebook_url,
        "instagram_url": client.instagram_url,
        "youtube_url": client.youtube_url,
        "linkedin_url": client.linkedin_url,
        "twitter_url": client.twitter_url,
        "tiktok_url": client.tiktok_url,
        "preferred_post_time": client.preferred_post_time.strftime('%H:%M') if client.preferred_post_time else None,
        "created_at": client.created_at,
        "updated_at": client.updated_at,
    }
