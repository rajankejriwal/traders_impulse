from django.urls import path

from start_docker import views


urlpatterns = [
    path("create_img/<str:img_id>", views.CreateImage.as_view()),
    path("run_docker/", views.RunDockerWithUniqueID.as_view()),
    path("views/logs/<container_id>", views.view_logs, name="view_logs"),
]
