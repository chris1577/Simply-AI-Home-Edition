import os
from app import create_app

# Create the Flask application
app = create_app(os.getenv('FLASK_ENV', 'development'))

if __name__ == '__main__':
    # Run the application
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('PORT', 8080)),
        debug=app.config['DEBUG']
    )
