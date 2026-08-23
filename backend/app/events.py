import json


class PubSubPublisher:
    def __init__(self, project: str, topic: str) -> None:
        from google.cloud import pubsub_v1

        self.publisher = pubsub_v1.PublisherClient()
        self.topic_path = self.publisher.topic_path(project, topic)

    def publish(self, maintenance_id: str, event_id: str) -> str:
        payload = json.dumps({
            "maintenance_id": maintenance_id,
            "event_id": event_id,
        }).encode()
        future = self.publisher.publish(
            self.topic_path,
            payload,
            maintenance_id=maintenance_id,
            event_id=event_id,
            event_type="maintenance.created",
        )
        return future.result(timeout=15)

