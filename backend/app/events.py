import json


class PubSubPublisher:
    def __init__(self, project: str, topic: str) -> None:
        from google.cloud import pubsub_v1

        self.publisher = pubsub_v1.PublisherClient()
        self.topic_path = self.publisher.topic_path(project, topic)

    def publish(self, incident_id: str) -> str:
        payload = json.dumps({"incident_id": incident_id}).encode()
        future = self.publisher.publish(
            self.topic_path,
            payload,
            incident_id=incident_id,
            event_type="incident.created",
        )
        return future.result(timeout=15)

