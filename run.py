from flask import Flask
import webview
from flask import render_template
import base64

class Api:
    def saveImage(self, image):
        path = self.save_file_dialog()   
        imgdata = base64.b64decode(image.replace('data:image/png;base64,', ''))
        with open(path, 'wb') as f:
            f.write(imgdata)
        return {'message':'image saved!'}

    def save_file_dialog(self):
        result = self.window.create_file_dialog(webview.SAVE_DIALOG, directory='/', save_filename='image.png')
        return result


server = Flask(__name__, template_folder='.',static_folder='./assets')

@server.route("/")
def index():
    return render_template('index.html')

if __name__ == '__main__':
    api = Api()
    window = webview.create_window('Photo Editor', server,js_api=api)
    api.window = window
    webview.start(gui='cef')








