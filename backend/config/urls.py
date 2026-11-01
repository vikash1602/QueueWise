from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from accounts.views import CsrfView, LoginView, LogoutView, MeView, RegisterView
from analytics.views import (
    AdminOverviewView,
    AnalyticsPeakHoursView,
    AnalyticsSummaryView,
    AnalyticsTrendsView,
)
from appointments.views import (
    AppointmentCancelView,
    AppointmentDetailView,
    AppointmentListCreateView,
)
from audit.views import AuditLogListView
from notifications.views import (
    NotificationListView,
    NotificationReadAllView,
    NotificationReadView,
)
from organizations.views import (
    MyBusinessHoursView,
    MyCustomersView,
    MyOrganizationView,
    MyServicesViewSet,
    MyStaffView,
    PublicAvailabilityView,
    PublicOrganizationDetailView,
    PublicOrganizationListView,
)
from queues.views import (
    MyQueueEntriesView,
    StaffCheckInListView,
    MyQueueEntryCancelView,
    MyQueueEntryStatusView,
    PublicNowServingView,
    StaffCallNextView,
    StaffCheckInView,
    StaffEntryActionView,
    StaffHistoryView,
    StaffQueueTodayView,
    StaffWalkInView,
)

auth_patterns = [
    path("register/", RegisterView.as_view()),
    path("login/", LoginView.as_view()),
    path("logout/", LogoutView.as_view()),
    path("me/", MeView.as_view()),
    path("csrf/", CsrfView.as_view()),
]

public_patterns = [
    path("organizations/", PublicOrganizationListView.as_view()),
    path("organizations/<int:org_id>/", PublicOrganizationDetailView.as_view()),
    path(
        "organizations/<int:org_id>/availability/",
        PublicAvailabilityView.as_view(),
    ),
    path("organizations/<int:org_id>/now-serving/", PublicNowServingView.as_view()),
]

customer_patterns = [
    path("appointments/", AppointmentListCreateView.as_view()),
    path("appointments/<int:appointment_id>/", AppointmentDetailView.as_view()),
    path(
        "appointments/<int:appointment_id>/cancel/",
        AppointmentCancelView.as_view(),
    ),
    path("queue/entries/", MyQueueEntriesView.as_view()),
    path("queue/entries/<int:entry_id>/", MyQueueEntryStatusView.as_view()),
    path("queue/entries/<int:entry_id>/cancel/", MyQueueEntryCancelView.as_view()),
    path("notifications/", NotificationListView.as_view()),
    path("notifications/<int:notification_id>/read/", NotificationReadView.as_view()),
    path("notifications/read-all/", NotificationReadAllView.as_view()),
]

staff_patterns = [
    path("my/organization/", MyOrganizationView.as_view()),
    path("my/services/", MyServicesViewSet.as_view()),
    path("my/services/<int:service_id>/", MyServicesViewSet.as_view()),
    path("my/business-hours/", MyBusinessHoursView.as_view()),
    path("my/staff/", MyStaffView.as_view()),
    path("my/customers/", MyCustomersView.as_view()),
    path("my/staff/<int:member_id>/", MyStaffView.as_view()),
    path("my/analytics/summary/", AnalyticsSummaryView.as_view()),
    path("my/analytics/overview/", AdminOverviewView.as_view()),
    path("my/analytics/trends/", AnalyticsTrendsView.as_view()),
    path("my/analytics/peak-hours/", AnalyticsPeakHoursView.as_view()),
    path("my/audit-logs/", AuditLogListView.as_view()),
    path("staff/queue/today/", StaffQueueTodayView.as_view()),
    path("staff/queue/check-ins/", StaffCheckInListView.as_view()),
    path("staff/queue/walk-in/", StaffWalkInView.as_view()),
    path("staff/queue/call-next/", StaffCallNextView.as_view()),
    path("staff/queue/check-in/<int:appointment_id>/", StaffCheckInView.as_view()),
    path(
        "staff/queue/entries/<int:entry_id>/<str:action>/",
        StaffEntryActionView.as_view(),
    ),
    path("staff/queue/history/", StaffHistoryView.as_view()),
]

api_patterns = (
    [path("auth/", include(auth_patterns))]
    + public_patterns
    + customer_patterns
    + staff_patterns
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(api_patterns)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]
