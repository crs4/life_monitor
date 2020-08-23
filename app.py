import ssl
from lifemonitor.app import create_app

# create an app instance
application = create_app()

if __name__ == '__main__':
    """ Start development server"""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain('./certs/lm.crt', './certs/lm.key')
    application.run(host="0.0.0.0", port=8000, ssl_context=context)
