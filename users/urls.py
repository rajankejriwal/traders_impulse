from django.urls import path
from users import views


urlpatterns = [
    path(
        "test/",
        views.TestAPI.as_view(),
        name="test",
    )
]
