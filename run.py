from lifemonitor import app, config

if __name__ == '__main__':
    """ Start development server"""
    app.create_app().run(host="0.0.0.0", port=8000, debug=config.is_debug_mode_enabled())
