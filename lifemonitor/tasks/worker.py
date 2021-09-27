
from ..app import create_app

app = create_app(worker=True)
app.app_context().push()

broker = app.broker
