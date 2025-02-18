from django.urls import path

from start_docker import views


urlpatterns = [
    path("create_img/<str:img_id>", views.CreateImage.as_view()),
    path("run_docker/<str:unique_id>", views.RunDockerWithUniqueID.as_view()),
]
