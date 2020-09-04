from lifemonitor import app

if __name__ == '__main__':
    """ Start development server"""
    app.create_app().run(host="0.0.0.0", port=8000)
