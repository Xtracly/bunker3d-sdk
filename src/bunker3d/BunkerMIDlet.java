package bunker3d;

import javax.microedition.midlet.MIDlet;
import javax.microedition.lcdui.Display;

public class BunkerMIDlet extends MIDlet {
    private EngineCanvas canvas;

    public void startApp() {
        if (canvas == null) {
            canvas = new EngineCanvas(this);
            Display.getDisplay(this).setCurrent(canvas);
            canvas.start();
        }
    }

    public void pauseApp() {
        if (canvas != null) {
            canvas.stop();
        }
    }

    public void destroyApp(boolean unconditional) {
        if (canvas != null) {
            canvas.stop();
        }
        notifyDestroyed();
    }
}
