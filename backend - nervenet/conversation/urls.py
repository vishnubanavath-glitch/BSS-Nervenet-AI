from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from conversation.controller import create_session_view, session_detail_view, send_message_view
from conversation.auth_views import register_view, me_view, logout_view, EmailTokenObtainPairView, CustomTokenRefreshView
from conversation.api_views import (
    wallet_balance_view,
    wallet_add_funds_view,
    models_list_view,
    file_upload_view,
    conversations_list_create_view,
    conversation_detail_view,
    conversation_messages_view,
    delete_message_view,
)
from conversation.admin_views import (
    admin_dashboard_view,
    admin_users_list_view,
    admin_user_detail_view,
    admin_user_credits_view,
    admin_providers_view,
    admin_provider_detail_view,
    admin_models_view,
    admin_model_detail_view,
    admin_subscriptions_view,
    admin_files_view,
    admin_logs_view,
    admin_tickets_view,
    admin_ticket_detail_view,
    admin_settings_view,
    admin_mcp_view,
    admin_mcp_detail_view,
    admin_mcp_test_view,
    admin_provider_quota_view,
)

urlpatterns = [
    # Legacy endpoints (for Streamlit app)
    path("sessions/", create_session_view, name="create_session"),
    path("sessions/<str:session_id>/", session_detail_view, name="session_detail"),
    path("sessions/<str:session_id>/messages/", send_message_view, name="send_message"),

    # Authentication & Profile
    path("auth/register", register_view, name="auth_register"),
    path("auth/login", EmailTokenObtainPairView.as_view(), name="auth_login"),
    path("auth/refresh", CustomTokenRefreshView.as_view(), name="auth_refresh"),
    path("auth/logout", logout_view, name="auth_logout"),
    path("users/me", me_view, name="users_me"),

    # Payments & Wallet
    path("payment/balance", wallet_balance_view, name="wallet_balance"),
    path("payment/add-funds", wallet_add_funds_view, name="wallet_add_funds"),

    # Model Listing
    path("models", models_list_view, name="models_list"),

    # File Uploads
    path("files/upload", file_upload_view, name="file_upload"),

    # Conversations & Messages (for React UI)
    path("conversations", conversations_list_create_view, name="conversations_list_create"),
    path("conversations/<str:conversation_id>", conversation_detail_view, name="conversation_detail"),
    path("conversations/<str:conversation_id>/messages", conversation_messages_view, name="conversation_messages"),
    path("conversations/<str:conversation_id>/messages/<str:message_id>", delete_message_view, name="delete_message"),

    # Admin Panel APIs
    path("admin/dashboard", admin_dashboard_view, name="admin_dashboard"),
    path("admin/users", admin_users_list_view, name="admin_users"),
    path("admin/users/<int:user_id>", admin_user_detail_view, name="admin_user_delete"),
    path("admin/users/<int:user_id>/ban", admin_user_detail_view, name="admin_user_ban"),
    path("admin/users/<int:user_id>/credits", admin_user_credits_view, name="admin_user_credits"),
    
    path("admin/providers", admin_providers_view, name="admin_providers"),
    path("admin/providers/<str:provider_id>", admin_provider_detail_view, name="admin_provider_detail"),
    path("admin/providers/<str:provider_id>/quota", admin_provider_quota_view, name="admin_provider_quota"),
    
    path("admin/models", admin_models_view, name="admin_models"),
    path("admin/models/<str:model_id>", admin_model_detail_view, name="admin_model_delete"),
    
    path("admin/subscriptions", admin_subscriptions_view, name="admin_subscriptions"),
    path("admin/files", admin_files_view, name="admin_files"),
    path("admin/logs", admin_logs_view, name="admin_logs"),
    
    path("admin/tickets", admin_tickets_view, name="admin_tickets"),
    path("admin/tickets/<str:ticket_id>", admin_ticket_detail_view, name="admin_ticket_detail"),
    
    path("admin/settings", admin_settings_view, name="admin_settings"),
    
    path("admin/mcp", admin_mcp_view, name="admin_mcp"),
    path("admin/mcp/<str:mcp_id>", admin_mcp_detail_view, name="admin_mcp_detail"),
    path("admin/mcp/<str:mcp_id>/test", admin_mcp_test_view, name="admin_mcp_test"),
]
