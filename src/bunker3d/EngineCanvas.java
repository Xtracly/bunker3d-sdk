package bunker3d;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.InputStream;
import javax.microedition.lcdui.Font;
import javax.microedition.lcdui.Graphics;
import javax.microedition.lcdui.game.GameCanvas;
import javax.microedition.media.Manager;
import javax.microedition.media.Player;
import javax.microedition.rms.RecordStore;

public class EngineCanvas extends GameCanvas implements Runnable {

    private static final int SCREEN_W = 240;
    private static final int SCREEN_H = 320;
    private static final int HUD_H = 44;
    private static final int VIEW_H = SCREEN_H - HUD_H;

    private static final int FP_SHIFT = 16;
    private static final int FP_ONE = 1 << FP_SHIFT;
    private static final int FP_HALF = FP_ONE >> 1;

    private static final int ANGLE_360 = 1024;
    private static final int ANGLE_90 = 256;
    private static final int ANGLE_MASK = 1023;

    private static final int TEX_SIZE = 64;
    private static final int TEX_SHIFT = 6;
    private static final int TEX_MASK = 63;
    private static final int TRANSPARENT_RGB565 = 0xF81F;

    private static final int SKY_W = 256;
    private static final int SKY_H = 128;

    private static final byte APP_MAIN_MENU = 0;
    private static final byte APP_LEVEL_SELECT = 1;
    private static final byte APP_GAMEPLAY = 2;
    private static final byte APP_PAUSE_MENU = 3;

    private static final int SFX_SHOOT = 0;
    private static final int SFX_DOOR = 1;
    private static final int SFX_PICKUP = 2;
    private static final int SFX_HURT = 3;
    private static final int SFX_BOOM = 4;

    private static final byte ENT_NONE = 0;
    private static final byte ENT_GUARD = 1;
    private static final byte ENT_MEDKIT = 2;
    private static final byte ENT_AMMO = 3;
    private static final byte ENT_BARREL = 4;

    private static final byte STATE_IDLE = 0;
    private static final byte STATE_CHASE = 1;
    private static final byte STATE_ATTACK = 2;
    private static final byte STATE_PAIN = 3;
    private static final byte STATE_DEAD = 4;

    private static final String RMS_NAME = "Bunker3DSave";

    private final BunkerMIDlet midlet;
    private volatile boolean running;
    private Thread gameThread;

    private byte appState = APP_MAIN_MENU;
    private int menuCursor = 0;
    private int levelSelectCursor = 0;

    private final int[] frameBuffer = new int[SCREEN_W * VIEW_H];
    private final int[] zBuffer = new int[SCREEN_W];

    // Таблиці тригонометрії та попередньо обчислених відстаней підлоги/стелі
    private final int[] sinTable = new int[ANGLE_360];
    private final int[] cosTable = new int[ANGLE_360];
    private final int[] rowDistTable = new int[VIEW_H];

    private int[][] wallTextures = new int[8][TEX_SIZE * TEX_SIZE];
    private int[][] spriteTextures = new int[9][TEX_SIZE * TEX_SIZE];
    private int[][] weaponTextures = new int[2][TEX_SIZE * TEX_SIZE];
    private int[][] skyTextures = new int[3][SKY_W * SKY_H];
    private int currentSkyId = 1;

    private String[] levelPaths = new String[]{"/level1.b3d"};
    private int currentLevelIdx = 0;
    private int unlockedLevelIdx = 0;
    private int savedLevelIdx = 0;
    private int savedHp = 100;
    private int savedAmmo = 35;
    private boolean hasSavedGame = false;
    private boolean levelCompleted = false;
    private boolean campaignCompleted = false;

    private boolean soundEnabled = true;
    private final Player[] sfxPlayers = new Player[5];

    // Шари карти B3D4: стіни, підлога, стеля, освітлення (0..40)
    private int mapW = 16;
    private int mapH = 16;
    private byte[] mapGrid;
    private byte[] floorGrid;
    private byte[] ceilGrid;
    private byte[] lightGrid;
    private int[] doorOffset;
    private byte[] doorState;
    private int[] doorTimer;

    private static final int MAX_ENTITIES = 128;
    private int numEntities = 0;
    private final byte[] entType = new byte[MAX_ENTITIES];
    private final int[] entX = new int[MAX_ENTITIES];
    private final int[] entY = new int[MAX_ENTITIES];
    private final byte[] entState = new byte[MAX_ENTITIES];
    private final int[] entHp = new int[MAX_ENTITIES];
    private final int[] entTimer = new int[MAX_ENTITIES];
    private final int[] entOrder = new int[MAX_ENTITIES];
    private final int[] entDist = new int[MAX_ENTITIES];

    private int posX = 2 * FP_ONE + FP_HALF;
    private int posY = 2 * FP_ONE + FP_HALF;
    private int playerAngle = 0;
    private int playerHp = 100;
    private int playerAmmo = 35;
    private int walkPhase = 0;
    private int weaponTimer = 0;
    private int flashColor = 0;
    private int flashTimer = 0;
    private int bannerTimer = 0;
    private int enemiesAlive = 0;

    private static final int MOVE_SPEED = 4600;
    private static final int ROT_SPEED = 14;
    private static final int PLAYER_RADIUS = 14000;
    private static final int ENEMY_SPEED = 2200;

    private boolean lowDetail = false;
    private boolean showMinimap = true;
    private int currentFps = 0;
    private int rngState = 0x1337BEEF;

    private boolean keyLeft, keyRight, keyUp, keyDown, keyStrafeL, keyStrafeR;

    public EngineCanvas(BunkerMIDlet midlet) {
        super(false);
        setFullScreenMode(true);
        this.midlet = midlet;
        initTables();
        loadAssetsPak("/assets.pak");
        loadLevelsIndex("/levels.idx");
        loadProgressRMS();
        initSoundEffects();
        loadLevelByIndex(savedLevelIdx, false);
        appState = APP_MAIN_MENU;
    }

    private int nextRandom() {
        rngState ^= (rngState << 13);
        rngState ^= (rngState >>> 17);
        rngState ^= (rngState << 5);
        return rngState & 0x7FFFFFFF;
    }

    private void initTables() {
        for (int i = 0; i < ANGLE_360; i++) {
            double rad = (i * 2.0 * Math.PI) / ANGLE_360;
            sinTable[i] = (int) (Math.sin(rad) * FP_ONE);
            cosTable[i] = (int) (Math.cos(rad) * FP_ONE);
        }
        int halfH = VIEW_H >> 1;
        for (int y = 0; y < VIEW_H; y++) {
            int dy = y - halfH;
            if (dy < 0) dy = -dy;
            if (dy == 0) dy = 1;
            rowDistTable[y] = (VIEW_H << (FP_SHIFT - 1)) / dy;
        }
    }

    private void initSoundEffects() {
        String[] files = {"/shoot.wav", "/door.wav", "/pickup.wav", "/hurt.wav", "/boom.wav"};
        for (int i = 0; i < files.length; i++) {
            try {
                InputStream is = getClass().getResourceAsStream(files[i]);
                if (is != null) {
                    Player p = Manager.createPlayer(is, "audio/x-wav");
                    p.realize();
                    p.prefetch();
                    sfxPlayers[i] = p;
                }
            } catch (Exception e) {
                sfxPlayers[i] = null;
            }
        }
    }

    private void playSfx(int sfxId) {
        if (!soundEnabled) return;
        try {
            Player p = (sfxId >= 0 && sfxId < sfxPlayers.length) ? sfxPlayers[sfxId] : null;
            if (p != null) {
                if (p.getState() == Player.STARTED) p.stop();
                p.setMediaTime(0);
                p.start();
                return;
            }
        } catch (Exception e) {
        }
        try {
            int note = 60, dur = 60;
            if (sfxId == SFX_SHOOT) { note = 48; dur = 50; }
            else if (sfxId == SFX_DOOR) { note = 40; dur = 120; }
            else if (sfxId == SFX_PICKUP) { note = 76; dur = 80; }
            else if (sfxId == SFX_HURT) { note = 52; dur = 90; }
            else if (sfxId == SFX_BOOM) { note = 36; dur = 160; }
            Manager.playTone(note, dur, 80);
        } catch (Exception e) {
        }
    }

    private void loadProgressRMS() {
        RecordStore rs = null;
        try {
            rs = RecordStore.openRecordStore(RMS_NAME, true);
            if (rs.getNumRecords() > 0) {
                byte[] data = rs.getRecord(1);
                DataInputStream dis = new DataInputStream(new ByteArrayInputStream(data));
                if (dis.readInt() == 0x42334453) {
                    hasSavedGame = dis.readBoolean();
                    savedLevelIdx = dis.readUnsignedByte();
                    unlockedLevelIdx = dis.readUnsignedByte();
                    savedHp = dis.readUnsignedByte();
                    savedAmmo = dis.readUnsignedShort();
                    soundEnabled = dis.readBoolean();
                    lowDetail = dis.readBoolean();
                    if (savedLevelIdx >= levelPaths.length) savedLevelIdx = 0;
                    if (unlockedLevelIdx >= levelPaths.length) unlockedLevelIdx = levelPaths.length - 1;
                    if (savedHp <= 0) savedHp = 100;
                }
                dis.close();
            }
        } catch (Exception e) {
        } finally {
            if (rs != null) {
                try { rs.closeRecordStore(); } catch (Exception e) {}
            }
        }
    }

    private void saveProgressRMS() {
        RecordStore rs = null;
        try {
            ByteArrayOutputStream baos = new ByteArrayOutputStream(16);
            DataOutputStream dos = new DataOutputStream(baos);
            dos.writeInt(0x42334453);
            dos.writeBoolean(hasSavedGame);
            dos.writeByte(savedLevelIdx);
            dos.writeByte(unlockedLevelIdx);
            dos.writeByte(savedHp);
            dos.writeShort(savedAmmo);
            dos.writeBoolean(soundEnabled);
            dos.writeBoolean(lowDetail);
            dos.flush();
            byte[] bytes = baos.toByteArray();

            rs = RecordStore.openRecordStore(RMS_NAME, true);
            if (rs.getNumRecords() == 0) {
                rs.addRecord(bytes, 0, bytes.length);
            } else {
                rs.setRecord(1, bytes, 0, bytes.length);
            }
        } catch (Exception e) {
        } finally {
            if (rs != null) {
                try { rs.closeRecordStore(); } catch (Exception e) {}
            }
        }
    }

    private void loadLevelsIndex(String idxPath) {
        try {
            InputStream is = getClass().getResourceAsStream(idxPath);
            if (is != null) {
                DataInputStream dis = new DataInputStream(is);
                if (dis.readByte() == 'B' && dis.readByte() == 'I' && dis.readByte() == 'D' && dis.readByte() == 'X') {
                    int count = dis.readUnsignedByte();
                    if (count > 0) {
                        levelPaths = new String[count];
                        for (int i = 0; i < count; i++) {
                            int len = dis.readUnsignedByte();
                            byte[] strBytes = new byte[len];
                            dis.readFully(strBytes);
                            levelPaths[i] = new String(strBytes, "ISO-8859-1");
                        }
                    }
                }
                dis.close();
            }
        } catch (Exception e) {
        }
    }

    private void loadLevelByIndex(int idx, boolean resetStats) {
        if (levelPaths == null || levelPaths.length == 0) return;
        if (idx < 0) idx = 0;
        if (idx >= levelPaths.length) idx = 0;
        currentLevelIdx = idx;
        if (currentLevelIdx > unlockedLevelIdx) unlockedLevelIdx = currentLevelIdx;
        levelCompleted = false;
        campaignCompleted = false;
        bannerTimer = 45;

        if (resetStats) {
            playerHp = 100;
            playerAmmo = 35;
        } else if (playerHp < 25) {
            playerHp = 25;
        }

        hasSavedGame = true;
        savedLevelIdx = currentLevelIdx;
        savedHp = playerHp;
        savedAmmo = playerAmmo;
        saveProgressRMS();

        loadLevel(levelPaths[currentLevelIdx]);
    }

    private void loadAssetsPak(String path) {
        try {
            InputStream is = getClass().getResourceAsStream(path);
            if (is != null) {
                DataInputStream dis = new DataInputStream(is);
                if (dis.readByte() == 'B' && dis.readByte() == 'P' && dis.readByte() == 'A' && dis.readByte() == 'K') {
                    int nWalls = dis.readUnsignedByte();
                    int nSprites = dis.readUnsignedByte();
                    int nWeapons = dis.readUnsignedByte();
                    int nSkies = dis.readUnsignedByte();

                    wallTextures = new int[nWalls][TEX_SIZE * TEX_SIZE];
                    spriteTextures = new int[nSprites][TEX_SIZE * TEX_SIZE];
                    weaponTextures = new int[nWeapons][TEX_SIZE * TEX_SIZE];
                    skyTextures = new int[nSkies][SKY_W * SKY_H];

                    for (int i = 0; i < nWalls; i++) readTexture565(dis, wallTextures[i], false);
                    for (int i = 0; i < nSprites; i++) readTexture565(dis, spriteTextures[i], true);
                    for (int i = 0; i < nWeapons; i++) readTexture565(dis, weaponTextures[i], true);
                    for (int i = 0; i < nSkies; i++) {
                        int len = SKY_W * SKY_H;
                        for (int p = 0; p < len; p++) {
                            int val = dis.readUnsignedShort();
                            int r = ((val >> 11) & 31) << 3;
                            int g = ((val >> 5) & 63) << 2;
                            int b = (val & 31) << 3;
                            skyTextures[i][p] = (r << 16) | (g << 8) | b;
                        }
                    }
                }
                dis.close();
            }
        } catch (Exception e) {
        }
    }

    private void readTexture565(DataInputStream dis, int[] dest, boolean allowTransparency) throws Exception {
        int len = TEX_SIZE * TEX_SIZE;
        for (int i = 0; i < len; i++) {
            int val = dis.readUnsignedShort();
            if (allowTransparency && val == TRANSPARENT_RGB565) {
                dest[i] = -1;
            } else {
                int r = ((val >> 11) & 31) << 3;
                int g = ((val >> 5) & 63) << 2;
                int b = (val & 31) << 3;
                dest[i] = (r << 16) | (g << 8) | b;
            }
        }
    }

    private void loadLevel(String resourcePath) {
        try {
            InputStream is = getClass().getResourceAsStream(resourcePath);
            if (is != null) {
                DataInputStream dis = new DataInputStream(is);
                byte b0 = dis.readByte(), b1 = dis.readByte(), b2 = dis.readByte(), b3 = dis.readByte();
                if (b0 == 'B' && b1 == '3' && b2 == 'D' && (b3 >= '1' && b3 <= '4')) {
                    mapW = dis.readUnsignedByte();
                    mapH = dis.readUnsignedByte();
                    int sx = dis.readUnsignedByte();
                    int sy = dis.readUnsignedByte();
                    playerAngle = dis.readUnsignedShort() & ANGLE_MASK;
                    currentSkyId = (b3 >= '3') ? dis.readUnsignedByte() : 0;
                    posX = sx * FP_ONE + FP_HALF;
                    posY = sy * FP_ONE + FP_HALF;

                    int total = mapW * mapH;
                    mapGrid = new byte[total];
                    floorGrid = new byte[total];
                    ceilGrid = new byte[total];
                    lightGrid = new byte[total];
                    doorOffset = new int[total];
                    doorState = new byte[total];
                    doorTimer = new int[total];

                    dis.readFully(mapGrid);
                    if (b3 == '4') {
                        dis.readFully(floorGrid);
                        dis.readFully(ceilGrid);
                        dis.readFully(lightGrid);
                    } else {
                        byte defCeil = (byte) (currentSkyId > 0 ? 0 : 7);
                        for (int i = 0; i < total; i++) {
                            floorGrid[i] = 6;
                            ceilGrid[i] = defCeil;
                            lightGrid[i] = 8;
                        }
                    }

                    numEntities = 0;
                    enemiesAlive = 0;
                    if (b3 >= '2') {
                        int count = dis.readUnsignedByte();
                        for (int i = 0; i < count && numEntities < MAX_ENTITIES; i++) {
                            byte type = dis.readByte();
                            int ex = dis.readUnsignedByte();
                            int ey = dis.readUnsignedByte();
                            spawnEntity(type, ex * FP_ONE + FP_HALF, ey * FP_ONE + FP_HALF);
                        }
                    }
                    dis.close();
                    return;
                }
                dis.close();
            }
        } catch (Exception e) {
        }
    }

    private void spawnEntity(byte type, int x, int y) {
        int id = numEntities++;
        entType[id] = type;
        entX[id] = x;
        entY[id] = y;
        entState[id] = STATE_IDLE;
        entTimer[id] = 0;
        if (type == ENT_GUARD) {
            entHp[id] = 30;
            enemiesAlive++;
        } else if (type == ENT_BARREL) {
            entHp[id] = 15;
        } else {
            entHp[id] = 1;
        }
    }

    public void start() {
        running = true;
        gameThread = new Thread(this);
        gameThread.start();
    }

    public void stop() {
        running = false;
        saveProgressRMS();
    }

    private boolean isSoftKey(int keyCode) {
        return keyCode == -6 || keyCode == -7 || keyCode == -21 || keyCode == -22;
    }

    protected void keyPressed(int keyCode) {
        int action = 0;
        try { action = getGameAction(keyCode); } catch (Exception e) {}

        if (appState == APP_MAIN_MENU) {
            if (keyCode == KEY_NUM2 || action == UP) menuCursor = (menuCursor + 5) % 6;
            else if (keyCode == KEY_NUM8 || action == DOWN) menuCursor = (menuCursor + 1) % 6;
            else if (keyCode == KEY_NUM5 || action == FIRE) executeMainMenuItem();
            return;
        }

        if (appState == APP_LEVEL_SELECT) {
            if (keyCode == KEY_NUM2 || action == UP || keyCode == KEY_NUM4 || action == LEFT) {
                if (levelSelectCursor > 0) levelSelectCursor--;
            } else if (keyCode == KEY_NUM8 || action == DOWN || keyCode == KEY_NUM6 || action == RIGHT) {
                if (levelSelectCursor < unlockedLevelIdx) levelSelectCursor++;
            } else if (keyCode == KEY_NUM5 || action == FIRE) {
                loadLevelByIndex(levelSelectCursor, true);
                appState = APP_GAMEPLAY;
            } else if (isSoftKey(keyCode) || keyCode == KEY_NUM0 || keyCode == KEY_STAR) {
                appState = APP_MAIN_MENU;
            }
            return;
        }

        if (appState == APP_PAUSE_MENU) {
            if (keyCode == KEY_NUM2 || action == UP) menuCursor = (menuCursor + 4) % 5;
            else if (keyCode == KEY_NUM8 || action == DOWN) menuCursor = (menuCursor + 1) % 5;
            else if (keyCode == KEY_NUM5 || action == FIRE) executePauseMenuItem();
            else if (isSoftKey(keyCode)) appState = APP_GAMEPLAY;
            return;
        }

        if (isSoftKey(keyCode)) {
            keyUp = keyDown = keyLeft = keyRight = keyStrafeL = keyStrafeR = false;
            menuCursor = 0;
            appState = APP_PAUSE_MENU;
            return;
        }

        if (playerHp <= 0) {
            if (keyCode == KEY_NUM5 || action == FIRE) loadLevelByIndex(currentLevelIdx, true);
            return;
        }

        if (levelCompleted) {
            if (keyCode == KEY_NUM5 || action == FIRE) {
                if (campaignCompleted) appState = APP_MAIN_MENU;
                else loadLevelByIndex(currentLevelIdx + 1, false);
            }
            return;
        }

        updateKey(keyCode, true);
        if (keyCode == KEY_NUM5 || action == FIRE) {
            if (!tryInteractTile()) fireWeapon();
        } else if (keyCode == KEY_NUM0) {
            tryInteractTile();
        } else if (keyCode == KEY_NUM7) {
            if (currentLevelIdx > 0) loadLevelByIndex(currentLevelIdx - 1, false);
        } else if (keyCode == KEY_NUM9) {
            if (currentLevelIdx + 1 < levelPaths.length) loadLevelByIndex(currentLevelIdx + 1, false);
        } else if (keyCode == KEY_STAR) {
            showMinimap = !showMinimap;
        } else if (keyCode == KEY_POUND) {
            lowDetail = !lowDetail;
            saveProgressRMS();
        }
    }

    private void executeMainMenuItem() {
        switch (menuCursor) {
            case 0:
                playerHp = savedHp;
                playerAmmo = savedAmmo;
                loadLevelByIndex(savedLevelIdx, false);
                appState = APP_GAMEPLAY;
                break;
            case 1:
                loadLevelByIndex(0, true);
                appState = APP_GAMEPLAY;
                break;
            case 2:
                levelSelectCursor = currentLevelIdx;
                if (levelSelectCursor > unlockedLevelIdx) levelSelectCursor = unlockedLevelIdx;
                appState = APP_LEVEL_SELECT;
                break;
            case 3:
                soundEnabled = !soundEnabled;
                saveProgressRMS();
                if (soundEnabled) playSfx(SFX_PICKUP);
                break;
            case 4:
                lowDetail = !lowDetail;
                saveProgressRMS();
                break;
            case 5:
                saveProgressRMS();
                midlet.destroyApp(true);
                break;
        }
    }

    private void executePauseMenuItem() {
        switch (menuCursor) {
            case 0:
                appState = APP_GAMEPLAY;
                break;
            case 1:
                loadLevelByIndex(currentLevelIdx, true);
                appState = APP_GAMEPLAY;
                break;
            case 2:
                soundEnabled = !soundEnabled;
                saveProgressRMS();
                break;
            case 3:
                lowDetail = !lowDetail;
                saveProgressRMS();
                break;
            case 4:
                savedLevelIdx = currentLevelIdx;
                savedHp = playerHp > 0 ? playerHp : 100;
                savedAmmo = playerAmmo;
                saveProgressRMS();
                menuCursor = 0;
                appState = APP_MAIN_MENU;
                break;
        }
    }

    protected void keyReleased(int keyCode) {
        if (appState == APP_GAMEPLAY) updateKey(keyCode, false);
    }

    private void updateKey(int keyCode, boolean pressed) {
        switch (keyCode) {
            case KEY_NUM2: keyUp = pressed; return;
            case KEY_NUM8: keyDown = pressed; return;
            case KEY_NUM4: keyLeft = pressed; return;
            case KEY_NUM6: keyRight = pressed; return;
            case KEY_NUM1: keyStrafeL = pressed; return;
            case KEY_NUM3: keyStrafeR = pressed; return;
        }
        int action = 0;
        try { action = getGameAction(keyCode); } catch (Exception e) {}
        switch (action) {
            case UP:    keyUp = pressed; break;
            case DOWN:  keyDown = pressed; break;
            case LEFT:  keyLeft = pressed; break;
            case RIGHT: keyRight = pressed; break;
        }
    }

    private boolean tryInteractTile() {
        int checkX = (posX + (cosTable[playerAngle] >> 1)) >> FP_SHIFT;
        int checkY = (posY + (sinTable[playerAngle] >> 1)) >> FP_SHIFT;
        if (checkX >= 0 && checkX < mapW && checkY >= 0 && checkY < mapH) {
            int idx = checkY * mapW + checkX;
            byte tile = mapGrid[idx];
            if (tile == 4) {
                if (doorState[idx] == 0 || doorState[idx] == 3) {
                    doorState[idx] = 1;
                    playSfx(SFX_DOOR);
                } else if (doorState[idx] == 2) {
                    doorState[idx] = 3;
                    playSfx(SFX_DOOR);
                }
                return true;
            } else if (tile == 5) {
                levelCompleted = true;
                campaignCompleted = (currentLevelIdx + 1 >= levelPaths.length);
                if (!campaignCompleted && currentLevelIdx + 1 > unlockedLevelIdx) {
                    unlockedLevelIdx = currentLevelIdx + 1;
                }
                savedLevelIdx = campaignCompleted ? 0 : (currentLevelIdx + 1);
                savedHp = playerHp;
                savedAmmo = playerAmmo;
                saveProgressRMS();
                playSfx(SFX_PICKUP);
                flashColor = 0x20E060;
                flashTimer = 4;
                keyUp = keyDown = keyLeft = keyRight = keyStrafeL = keyStrafeR = false;
                return true;
            }
        }
        return false;
    }

    private void fireWeapon() {
        if (weaponTimer > 0 || playerAmmo <= 0) return;
        playerAmmo--;
        weaponTimer = 6;
        playSfx(SFX_SHOOT);

        int dirX = cosTable[playerAngle];
        int dirY = sinTable[playerAngle];
        int centerCol = SCREEN_W >> 1;
        int maxRange = zBuffer[centerCol];

        int bestEnt = -1;
        int bestDist = maxRange;

        for (int i = 0; i < numEntities; i++) {
            byte t = entType[i];
            if ((t != ENT_GUARD && t != ENT_BARREL) || entState[i] == STATE_DEAD) continue;

            int relX = entX[i] - posX;
            int relY = entY[i] - posY;
            int transY = (int) (((long) relX * dirX + (long) relY * dirY) >> FP_SHIFT);
            if (transY <= 4096 || transY >= bestDist) continue;

            int rightDist = (int) (((long) -relX * dirY + (long) relY * dirX) >> FP_SHIFT);
            int screenX = centerCol + (int) ((((long) rightDist * 3 * centerCol) >> 1) / transY);
            int spriteHalfW = ((VIEW_H << FP_SHIFT) / transY) >> 2;
            if (spriteHalfW < 8) spriteHalfW = 8;

            if (screenX >= centerCol - spriteHalfW && screenX <= centerCol + spriteHalfW) {
                bestDist = transY;
                bestEnt = i;
            }
        }

        for (int i = 0; i < numEntities; i++) {
            if (entType[i] == ENT_GUARD && entState[i] == STATE_IDLE) {
                if (hasLineOfSight(posX, posY, entX[i], entY[i])) entState[i] = STATE_CHASE;
            }
        }

        if (bestEnt != -1) damageEntity(bestEnt, 15);
    }

    private void damageEntity(int id, int dmg) {
        if (entState[id] == STATE_DEAD) return;
        entHp[id] -= dmg;
        if (entHp[id] <= 0) {
            entHp[id] = 0;
            entState[id] = STATE_DEAD;
            entTimer[id] = 0;
            if (entType[id] == ENT_GUARD) {
                enemiesAlive--;
            } else if (entType[id] == ENT_BARREL) {
                playSfx(SFX_BOOM);
                flashColor = 0xFF8800;
                flashTimer = 3;
                for (int j = 0; j < numEntities; j++) {
                    if (j == id || entState[j] == STATE_DEAD) continue;
                    if (entType[j] == ENT_GUARD || entType[j] == ENT_BARREL) {
                        int dx = (entX[j] - entX[id]) >> FP_SHIFT;
                        int dy = (entY[j] - entY[id]) >> FP_SHIFT;
                        if (dx * dx + dy * dy <= 6) damageEntity(j, 35);
                    }
                }
            }
        } else if (entType[id] == ENT_GUARD) {
            entState[id] = STATE_PAIN;
            entTimer[id] = 6;
        }
    }

    private boolean hasLineOfSight(int x0, int y0, int x1, int y1) {
        int steps = 12;
        int dx = (x1 - x0) / steps;
        int dy = (y1 - y0) / steps;
        int cx = x0, cy = y0;
        for (int i = 1; i < steps; i++) {
            cx += dx;
            cy += dy;
            if (!isPassable(cx >> FP_SHIFT, cy >> FP_SHIFT)) return false;
        }
        return true;
    }

    private void updateLogic() {
        if (appState == APP_MAIN_MENU || appState == APP_LEVEL_SELECT) {
            playerAngle = (playerAngle + 3) & ANGLE_MASK;
            return;
        }
        if (appState == APP_PAUSE_MENU) return;

        if (weaponTimer > 0) weaponTimer--;
        if (flashTimer > 0) flashTimer--;
        if (bannerTimer > 0) bannerTimer--;
        if (playerHp <= 0 || levelCompleted) return;

        if (keyLeft) playerAngle = (playerAngle - ROT_SPEED) & ANGLE_MASK;
        if (keyRight) playerAngle = (playerAngle + ROT_SPEED) & ANGLE_MASK;

        int moveX = 0, moveY = 0;
        if (keyUp) {
            moveX += (int) (((long) cosTable[playerAngle] * MOVE_SPEED) >> FP_SHIFT);
            moveY += (int) (((long) sinTable[playerAngle] * MOVE_SPEED) >> FP_SHIFT);
        }
        if (keyDown) {
            moveX -= (int) (((long) cosTable[playerAngle] * MOVE_SPEED) >> FP_SHIFT);
            moveY -= (int) (((long) sinTable[playerAngle] * MOVE_SPEED) >> FP_SHIFT);
        }
        if (keyStrafeL) {
            int ang = (playerAngle - ANGLE_90) & ANGLE_MASK;
            moveX += (int) (((long) cosTable[ang] * MOVE_SPEED) >> FP_SHIFT);
            moveY += (int) (((long) sinTable[ang] * MOVE_SPEED) >> FP_SHIFT);
        }
        if (keyStrafeR) {
            int ang = (playerAngle + ANGLE_90) & ANGLE_MASK;
            moveX += (int) (((long) cosTable[ang] * MOVE_SPEED) >> FP_SHIFT);
            moveY += (int) (((long) sinTable[ang] * MOVE_SPEED) >> FP_SHIFT);
        }

        if (moveX != 0 || moveY != 0) {
            walkPhase = (walkPhase + 48) & ANGLE_MASK;
            if (moveX != 0) {
                int nextX = posX + moveX;
                int marginX = moveX > 0 ? PLAYER_RADIUS : -PLAYER_RADIUS;
                if (isPassable((nextX + marginX) >> FP_SHIFT, posY >> FP_SHIFT) && !isBlockedByEntity(nextX, posY, -1)) {
                    posX = nextX;
                }
            }
            if (moveY != 0) {
                int nextY = posY + moveY;
                int marginY = moveY > 0 ? PLAYER_RADIUS : -PLAYER_RADIUS;
                if (isPassable(posX >> FP_SHIFT, (nextY + marginY) >> FP_SHIFT) && !isBlockedByEntity(posX, nextY, -1)) {
                    posY = nextY;
                }
            }
        } else {
            walkPhase = 0;
        }

        int total = mapW * mapH;
        int pCellX = posX >> FP_SHIFT;
        int pCellY = posY >> FP_SHIFT;
        for (int i = 0; i < total; i++) {
            if (mapGrid[i] != 4) continue;
            if (doorState[i] == 1) {
                doorOffset[i] += 4096;
                if (doorOffset[i] >= FP_ONE) {
                    doorOffset[i] = FP_ONE;
                    doorState[i] = 2;
                    doorTimer[i] = 90;
                }
            } else if (doorState[i] == 2) {
                if (doorTimer[i] > 0) {
                    doorTimer[i]--;
                } else if ((i % mapW) != pCellX || (i / mapW) != pCellY) {
                    doorState[i] = 3;
                    playSfx(SFX_DOOR);
                }
            } else if (doorState[i] == 3) {
                doorOffset[i] -= 4096;
                if (doorOffset[i] <= 0) {
                    doorOffset[i] = 0;
                    doorState[i] = 0;
                }
            }
        }

        for (int i = 0; i < numEntities; i++) {
            byte t = entType[i];
            if (t == ENT_NONE) continue;

            int dx = posX - entX[i];
            int dy = posY - entY[i];
            int absDx = dx < 0 ? -dx : dx;
            int absDy = dy < 0 ? -dy : dy;

            if (t == ENT_MEDKIT && absDx < 36000 && absDy < 36000) {
                if (playerHp < 100) {
                    playerHp += 25;
                    if (playerHp > 100) playerHp = 100;
                    entType[i] = ENT_NONE;
                    flashColor = 0x20D040;
                    flashTimer = 3;
                    playSfx(SFX_PICKUP);
                }
                continue;
            }
            if (t == ENT_AMMO && absDx < 36000 && absDy < 36000) {
                playerAmmo += 15;
                entType[i] = ENT_NONE;
                flashColor = 0xE0C030;
                flashTimer = 3;
                playSfx(SFX_PICKUP);
                continue;
            }

            if (t != ENT_GUARD || entState[i] == STATE_DEAD) continue;

            if (entTimer[i] > 0) {
                entTimer[i]--;
                if (entTimer[i] == 0 && (entState[i] == STATE_PAIN || entState[i] == STATE_ATTACK)) {
                    entState[i] = STATE_CHASE;
                }
                continue;
            }

            if (entState[i] == STATE_IDLE) {
                if (absDx < 7 * FP_ONE && absDy < 7 * FP_ONE && hasLineOfSight(entX[i], entY[i], posX, posY)) {
                    entState[i] = STATE_CHASE;
                }
            } else if (entState[i] == STATE_CHASE) {
                boolean canSee = hasLineOfSight(entX[i], entY[i], posX, posY);
                if (canSee && absDx < 5 * FP_ONE && absDy < 5 * FP_ONE && (nextRandom() % 18 == 0)) {
                    entState[i] = STATE_ATTACK;
                    entTimer[i] = 8;
                    int dmg = 5 + (nextRandom() % 7);
                    playerHp -= dmg;
                    if (playerHp < 0) playerHp = 0;
                    flashColor = 0xD02020;
                    flashTimer = 3;
                    playSfx(SFX_HURT);
                } else if (absDx > FP_ONE || absDy > FP_ONE) {
                    int stepX = dx > 8000 ? ENEMY_SPEED : (dx < -8000 ? -ENEMY_SPEED : 0);
                    int stepY = dy > 8000 ? ENEMY_SPEED : (dy < -8000 ? -ENEMY_SPEED : 0);
                    int margin = 12000;

                    if (stepX != 0) {
                        int nx = entX[i] + stepX;
                        int mx = stepX > 0 ? margin : -margin;
                        if (isPassable((nx + mx) >> FP_SHIFT, entY[i] >> FP_SHIFT) && !isBlockedByEntity(nx, entY[i], i)) {
                            entX[i] = nx;
                        }
                    }
                    if (stepY != 0) {
                        int ny = entY[i] + stepY;
                        int my = stepY > 0 ? margin : -margin;
                        if (isPassable(entX[i] >> FP_SHIFT, (ny + my) >> FP_SHIFT) && !isBlockedByEntity(entX[i], ny, i)) {
                            entY[i] = ny;
                        }
                    }
                    entTimer[i] = (entTimer[i] + 1) & 15;
                }
            }
        }
    }

    private boolean isBlockedByEntity(int x, int y, int ignoreId) {
        for (int i = 0; i < numEntities; i++) {
            if (i == ignoreId || entState[i] == STATE_DEAD) continue;
            byte t = entType[i];
            if (t == ENT_GUARD || t == ENT_BARREL) {
                int dx = x - entX[i];
                int dy = y - entY[i];
                if (dx > -22000 && dx < 22000 && dy > -22000 && dy < 22000) return true;
            }
        }
        return false;
    }

    private boolean isPassable(int cellX, int cellY) {
        if (cellX < 0 || cellX >= mapW || cellY < 0 || cellY >= mapH) return false;
        int idx = cellY * mapW + cellX;
        byte cell = mapGrid[idx];
        if (cell == 0) return true;
        if (cell == 4 && doorOffset[idx] > (FP_ONE * 3 / 4)) return true;
        return false;
    }

    private void render3D() {
        int halfH = VIEW_H >> 1;
        int stepPixels = lowDetail ? 2 : 1;
        int dirX = cosTable[playerAngle];
        int dirY = sinTable[playerAngle];
        int planeX = (sinTable[playerAngle] * 2) / 3;
        int planeY = (-cosTable[playerAngle] * 2) / 3;

        int skyIdx = (currentSkyId > 0 && currentSkyId <= skyTextures.length) ? (currentSkyId - 1) : 0;
        int[] activeSky = (skyTextures.length > 0) ? skyTextures[skyIdx] : null;
        int skyAngleOffset = (playerAngle >> 1);
        int numWallTex = wallTextures.length;

        for (int x = 0; x < SCREEN_W; x += stepPixels) {
            int cameraX = ((x << 1) - SCREEN_W) * FP_ONE / SCREEN_W;
            int rayDirX = dirX - (int) (((long) planeX * cameraX) >> FP_SHIFT);
            int rayDirY = dirY - (int) (((long) planeY * cameraX) >> FP_SHIFT);

            int mapX = posX >> FP_SHIFT;
            int mapY = posY >> FP_SHIFT;

            int absRayX = rayDirX < 0 ? -rayDirX : rayDirX;
            int absRayY = rayDirY < 0 ? -rayDirY : rayDirY;

            int deltaDistX = (absRayX < 8) ? 0x3FFFFFFF : (int) (((long) FP_ONE << FP_SHIFT) / absRayX);
            int deltaDistY = (absRayY < 8) ? 0x3FFFFFFF : (int) (((long) FP_ONE << FP_SHIFT) / absRayY);

            int stepX, stepY, sideDistX, sideDistY;
            if (rayDirX < 0) {
                stepX = -1;
                sideDistX = (int) (((long) (posX - (mapX << FP_SHIFT)) * deltaDistX) >> FP_SHIFT);
            } else {
                stepX = 1;
                sideDistX = (int) (((long) (((mapX + 1) << FP_SHIFT) - posX) * deltaDistX) >> FP_SHIFT);
            }
            if (rayDirY < 0) {
                stepY = -1;
                sideDistY = (int) (((long) (posY - (mapY << FP_SHIFT)) * deltaDistY) >> FP_SHIFT);
            } else {
                stepY = 1;
                sideDistY = (int) (((long) (((mapY + 1) << FP_SHIFT) - posY) * deltaDistY) >> FP_SHIFT);
            }

            int hitTile = 0, side = 0, perpWallDist = FP_ONE, wallX = 0;
            int hitCellIdx = 0;
            int maxSteps = 128;
            while (maxSteps-- > 0) {
                if (sideDistX < sideDistY) {
                    sideDistX += deltaDistX;
                    mapX += stepX;
                    side = 0;
                } else {
                    sideDistY += deltaDistY;
                    mapY += stepY;
                    side = 1;
                }

                if (mapX < 0 || mapX >= mapW || mapY < 0 || mapY >= mapH) {
                    hitTile = 1;
                    perpWallDist = (side == 0) ? (sideDistX - deltaDistX) : (sideDistY - deltaDistY);
                    break;
                }

                int cellIdx = mapY * mapW + mapX;
                byte tile = mapGrid[cellIdx];
                if (tile > 0) {
                    if (tile == 4) {
                        int dDist = (side == 0) ? (sideDistX - (deltaDistX >> 1)) : (sideDistY - (deltaDistY >> 1));
                        int hitCoord = (side == 0)
                                ? posY + (int) (((long) dDist * rayDirY) >> FP_SHIFT)
                                : posX + (int) (((long) dDist * rayDirX) >> FP_SHIFT);
                        int cellCoord = hitCoord & (FP_ONE - 1);
                        if (cellCoord >= doorOffset[cellIdx]) {
                            hitTile = 4;
                            hitCellIdx = cellIdx;
                            perpWallDist = dDist;
                            wallX = (cellCoord - doorOffset[cellIdx]) & (FP_ONE - 1);
                            break;
                        }
                    } else {
                        hitTile = tile;
                        hitCellIdx = cellIdx;
                        perpWallDist = (side == 0) ? (sideDistX - deltaDistX) : (sideDistY - deltaDistY);
                        wallX = (side == 0)
                                ? posY + (int) (((long) perpWallDist * rayDirY) >> FP_SHIFT)
                                : posX + (int) (((long) perpWallDist * rayDirX) >> FP_SHIFT);
                        wallX &= (FP_ONE - 1);
                        break;
                    }
                }
            }
            if (hitTile == 0) {
                perpWallDist = 64 * FP_ONE; // Максимальна далечінь горизонту
            }

            if (perpWallDist < 2048) perpWallDist = 2048;
            zBuffer[x] = perpWallDist;
            if (lowDetail && x + 1 < SCREEN_W) zBuffer[x + 1] = perpWallDist;

            int lineHeight = (VIEW_H << FP_SHIFT) / perpWallDist;
            int drawStart = halfH - (lineHeight >> 1);
            int drawEnd = halfH + (lineHeight >> 1);
            if (drawStart < 0) drawStart = 0;
            if (drawEnd >= VIEW_H) drawEnd = VIEW_H - 1;

            // 1. Вертикальний рендер текстурованої стелі (або Skybox, якщо ceil == 0) та підлоги
            int skyX = (skyAngleOffset + x) & 255;

            // Стеля: рядки [0 .. drawStart - 1]
            int fbCeilIdx = x;
            for (int y = 0; y < drawStart; y++) {
                int dist = rowDistTable[y];
                int wx = posX + (int) (((long) dist * rayDirX) >> FP_SHIFT);
                int wy = posY + (int) (((long) dist * rayDirY) >> FP_SHIFT);
                int cx = (wx >> FP_SHIFT);
                int cy = (wy >> FP_SHIFT);
                int cColor;
                if (cx >= 0 && cx < mapW && cy >= 0 && cy < mapH) {
                    int cIdx = cy * mapW + cx;
                    int ceilTexId = ceilGrid[cIdx] & 0xFF;
                    if (ceilTexId == 0) {
                        // Відкрите небо (SKY) у цій клітинці
                        if (activeSky != null) {
                            int skyY = (y * SKY_H) / halfH;
                            cColor = activeSky[skyY * SKY_W + skyX];
                        } else {
                            cColor = 0x142030;
                        }
                    } else {
                        int tId = (ceilTexId - 1) % numWallTex;
                        int tx = (wx >> 10) & TEX_MASK;
                        int ty = (wy >> 10) & TEX_MASK;
                        int fog = (dist >> (FP_SHIFT + 1)) + ((lightGrid[cIdx] & 0xFF) >> 3);
                        cColor = applyFog(wallTextures[tId][(ty << TEX_SHIFT) + tx], fog);
                    }
                } else if (activeSky != null) {
                    int skyY = (y * SKY_H) / halfH;
                    cColor = activeSky[skyY * SKY_W + skyX];
                } else {
                    cColor = 0x141A20;
                }
                frameBuffer[fbCeilIdx] = cColor;
                if (lowDetail && x + 1 < SCREEN_W) frameBuffer[fbCeilIdx + 1] = cColor;
                fbCeilIdx += SCREEN_W;
            }

            // 2. Рендер стіни: рядки [drawStart .. drawEnd]
            if (hitTile > 0) {
                int texId = (hitTile - 1) % numWallTex;
                int[] tex = wallTextures[texId];

                int texX = (wallX * TEX_SIZE) >> FP_SHIFT;
                if (hitTile != 4 && ((side == 0 && rayDirX > 0) || (side == 1 && rayDirY < 0))) {
                    texX = TEX_SIZE - texX - 1;
                }
                texX &= TEX_MASK;

                int texStep = (TEX_SIZE << FP_SHIFT) / lineHeight;
                int texPos = (drawStart - halfH + (lineHeight >> 1)) * texStep;

                int adjX = mapX - (side == 0 ? stepX : 0);
                int adjY = mapY - (side == 1 ? stepY : 0);
                int cellLight = 8;
                if (adjX >= 0 && adjX < mapW && adjY >= 0 && adjY < mapH) {
                    cellLight = lightGrid[adjY * mapW + adjX] & 0xFF;
                } else {
                    cellLight = lightGrid[hitCellIdx] & 0xFF;
                }
                int fogLevel = (perpWallDist >> (FP_SHIFT + 1)) + (cellLight >> 3) + (side == 1 ? 1 : 0);

                int fbWallIdx = drawStart * SCREEN_W + x;
                for (int y = drawStart; y <= drawEnd; y++) {
                    int texY = (texPos >> FP_SHIFT) & TEX_MASK;
                    texPos += texStep;
                    int color = applyFog(tex[(texY << TEX_SHIFT) + texX], fogLevel);
                    frameBuffer[fbWallIdx] = color;
                    if (lowDetail && x + 1 < SCREEN_W) frameBuffer[fbWallIdx + 1] = color;
                    fbWallIdx += SCREEN_W;
                }
            }

            // 3. Підлога: рядки [drawEnd + 1 .. VIEW_H - 1]
            int fbFloorIdx = (drawEnd + 1) * SCREEN_W + x;
            for (int y = drawEnd + 1; y < VIEW_H; y++) {
                int dist = rowDistTable[y];
                int wx = posX + (int) (((long) dist * rayDirX) >> FP_SHIFT);
                int wy = posY + (int) (((long) dist * rayDirY) >> FP_SHIFT);
                int cx = (wx >> FP_SHIFT);
                int cy = (wy >> FP_SHIFT);
                int fColor;
                if (cx >= 0 && cx < mapW && cy >= 0 && cy < mapH) {
                    int cIdx = cy * mapW + cx;
                    int flrTexId = floorGrid[cIdx] & 0xFF;
                    if (flrTexId <= 0) flrTexId = 6;
                    int tId = (flrTexId - 1) % numWallTex;
                    int tx = (wx >> 10) & TEX_MASK;
                    int ty = (wy >> 10) & TEX_MASK;
                    int fog = (dist >> (FP_SHIFT + 1)) + ((lightGrid[cIdx] & 0xFF) >> 3);
                    fColor = applyFog(wallTextures[tId][(ty << TEX_SHIFT) + tx], fog);
                } else {
                    fColor = 0x1A1E1C;
                }
                frameBuffer[fbFloorIdx] = fColor;
                if (lowDetail && x + 1 < SCREEN_W) frameBuffer[fbFloorIdx + 1] = fColor;
                fbFloorIdx += SCREEN_W;
            }
        }

        renderSprites(dirX, dirY, halfH);

        if (appState == APP_GAMEPLAY) {
            renderWeapon();
            if (flashTimer > 0) {
                int len = SCREEN_W * VIEW_H;
                for (int i = 0; i < len; i++) {
                    frameBuffer[i] = ((frameBuffer[i] >> 1) & 0x7F7F7F) + ((flashColor >> 1) & 0x7F7F7F);
                }
            }
        } else {
            int len = SCREEN_W * VIEW_H;
            for (int i = 0; i < len; i++) {
                frameBuffer[i] = (frameBuffer[i] >> 2) & 0x3F3F3F;
            }
        }
    }

    private int applyFog(int color, int fogLevel) {
        if (fogLevel <= 0) return color;
        if (fogLevel == 1) return (color >> 1) & 0x7F7F7F;
        if (fogLevel == 2) return ((color >> 1) & 0x7F7F7F) - ((color >> 3) & 0x1F1F1F);
        if (fogLevel == 3) return (color >> 2) & 0x3F3F3F;
        return (color >> 3) & 0x1F1F1F;
    }

    private void renderSprites(int dirX, int dirY, int halfH) {
        int visibleCount = 0;
        for (int i = 0; i < numEntities; i++) {
            if (entType[i] == ENT_NONE) continue;
            int relX = entX[i] - posX;
            int relY = entY[i] - posY;
            int transY = (int) (((long) relX * dirX + (long) relY * dirY) >> FP_SHIFT);
            if (transY > 4096) {
                entOrder[visibleCount] = i;
                entDist[visibleCount] = transY;
                visibleCount++;
            }
        }

        for (int i = 1; i < visibleCount; i++) {
            int keyDist = entDist[i];
            int keyOrd = entOrder[i];
            int j = i - 1;
            while (j >= 0 && entDist[j] < keyDist) {
                entDist[j + 1] = entDist[j];
                entOrder[j + 1] = entOrder[j];
                j--;
            }
            entDist[j + 1] = keyDist;
            entOrder[j + 1] = keyOrd;
        }

        int centerCol = SCREEN_W >> 1;
        for (int idx = 0; idx < visibleCount; idx++) {
            int id = entOrder[idx];
            int transY = entDist[idx];
            int relX = entX[id] - posX;
            int relY = entY[id] - posY;

            int rightDist = (int) (((long) -relX * dirY + (long) relY * dirX) >> FP_SHIFT);
            int spriteScreenX = centerCol + (int) ((((long) rightDist * 3 * centerCol) >> 1) / transY);

            int spriteSize = (VIEW_H << FP_SHIFT) / transY;
            int halfSprite = spriteSize >> 1;

            int drawStartY = halfH - halfSprite;
            int drawEndY = halfH + halfSprite;
            if (drawStartY < 0) drawStartY = 0;
            if (drawEndY >= VIEW_H) drawEndY = VIEW_H - 1;

            int drawStartX = spriteScreenX - halfSprite;
            int drawEndX = spriteScreenX + halfSprite;
            if (drawStartX < 0) drawStartX = 0;
            if (drawEndX >= SCREEN_W) drawEndX = SCREEN_W - 1;

            int[] tex = spriteTextures[getSpriteFrameIndex(id)];
            int exCell = entX[id] >> FP_SHIFT;
            int eyCell = entY[id] >> FP_SHIFT;
            int entLight = (exCell >= 0 && exCell < mapW && eyCell >= 0 && eyCell < mapH)
                    ? (lightGrid[eyCell * mapW + exCell] & 0xFF)
                    : 8;
            int fogLevel = (transY >> (FP_SHIFT + 1)) + (entLight >> 3);
            int step = (TEX_SIZE << FP_SHIFT) / spriteSize;

            for (int stripe = drawStartX; stripe <= drawEndX; stripe++) {
                if (transY >= zBuffer[stripe]) continue;

                int texX = (((stripe - (spriteScreenX - halfSprite)) * step) >> FP_SHIFT) & TEX_MASK;
                int texPos = (drawStartY - (halfH - halfSprite)) * step;
                int fbIdx = drawStartY * SCREEN_W + stripe;

                for (int y = drawStartY; y <= drawEndY; y++) {
                    int texY = (texPos >> FP_SHIFT) & TEX_MASK;
                    texPos += step;
                    int color = tex[(texY << TEX_SHIFT) + texX];
                    if (color != -1) {
                        frameBuffer[fbIdx] = applyFog(color, fogLevel);
                    }
                    fbIdx += SCREEN_W;
                }
            }
        }
    }

    private int getSpriteFrameIndex(int id) {
        byte t = entType[id];
        if (t == ENT_MEDKIT) return 5;
        if (t == ENT_AMMO) return 6;
        if (t == ENT_BARREL) return (entState[id] == STATE_DEAD) ? 8 : 7;

        byte st = entState[id];
        if (st == STATE_DEAD) return 4;
        if (st == STATE_PAIN) return 3;
        if (st == STATE_ATTACK) return 2;
        if (st == STATE_CHASE && ((System.currentTimeMillis() >> 8) & 1) == 1) return 1;
        return 0;
    }

    private void renderWeapon() {
        int frame = (weaponTimer > 2) ? 1 : 0;
        int[] tex = weaponTextures[frame];
        int bobX = (sinTable[walkPhase] * 6) >> FP_SHIFT;
        int bobY = Math.abs((cosTable[walkPhase] * 5) >> FP_SHIFT);

        int scale = 2;
        int drawW = TEX_SIZE * scale;
        int drawH = TEX_SIZE * scale;
        int startX = ((SCREEN_W - drawW) >> 1) + bobX;
        int startY = VIEW_H - drawH + bobY;

        for (int ty = 0; ty < TEX_SIZE; ty++) {
            int sy = startY + ty * scale;
            if (sy >= VIEW_H) break;
            for (int tx = 0; tx < TEX_SIZE; tx++) {
                int color = tex[(ty << TEX_SHIFT) + tx];
                if (color == -1) continue;
                int sx = startX + tx * scale;
                for (int dy = 0; dy < scale && (sy + dy) < VIEW_H; dy++) {
                    if (sy + dy < 0) continue;
                    int rowOff = (sy + dy) * SCREEN_W;
                    for (int dx = 0; dx < scale; dx++) {
                        int px = sx + dx;
                        if (px >= 0 && px < SCREEN_W) frameBuffer[rowOff + px] = color;
                    }
                }
            }
        }
    }

    private void drawMinimap(Graphics g) {
        int maxDim = mapW > mapH ? mapW : mapH;
        int scale = (maxDim <= 16) ? 4 : (maxDim <= 24 ? 3 : 2);
        int ox = 6, oy = 6;
        for (int my = 0; my < mapH; my++) {
            for (int mx = 0; mx < mapW; mx++) {
                byte tile = mapGrid[my * mapW + mx];
                if (tile == 0) g.setColor(0x101810);
                else if (tile == 4) g.setColor(0x20B040);
                else if (tile == 5) g.setColor(0xFF4040);
                else g.setColor(0x587058);
                g.fillRect(ox + mx * scale, oy + my * scale, scale, scale);
            }
        }
        for (int i = 0; i < numEntities; i++) {
            if (entType[i] == ENT_GUARD && entState[i] != STATE_DEAD) {
                g.setColor(0xFF3030);
                g.fillRect(ox + ((entX[i] * scale) >> FP_SHIFT) - 1, oy + ((entY[i] * scale) >> FP_SHIFT) - 1, 2, 2);
            }
        }
        g.setColor(0xFFCC00);
        g.fillRect(ox + ((posX * scale) >> FP_SHIFT) - 1, oy + ((posY * scale) >> FP_SHIFT) - 1, 3, 3);
    }

    private void drawMenuOverlay(Graphics g) {
        g.setColor(0x121814);
        g.fillRect(0, VIEW_H, SCREEN_W, HUD_H);
        g.setColor(0x3A5040);
        g.drawRect(0, VIEW_H, SCREEN_W - 1, HUD_H - 1);

        g.setColor(0x18261C);
        g.fillRect(24, 18, 192, 42);
        g.setColor(0x50C868);
        g.drawRect(24, 18, 192, 42);

        g.setFont(Font.getFont(Font.FACE_MONOSPACE, Font.STYLE_BOLD, Font.SIZE_LARGE));
        g.setColor(0x70FF88);
        g.drawString("BUNKER 3D", 64, 24, Graphics.TOP | Graphics.LEFT);

        g.setFont(Font.getFont(Font.FACE_MONOSPACE, Font.STYLE_PLAIN, Font.SIZE_SMALL));
        g.setColor(0x90B898);
        g.drawString("NOKIA S40 ENGINE", 64, 44, Graphics.TOP | Graphics.LEFT);

        if (appState == APP_MAIN_MENU) {
            String[] items = {
                "CONTINUE (SEC " + (savedLevelIdx + 1) + ")",
                "NEW CAMPAIGN",
                "SELECT SECTOR",
                "SOUND: " + (soundEnabled ? "ON" : "OFF"),
                "DETAIL: " + (lowDetail ? "2X TURBO" : "1X HIGH"),
                "EXIT GAME"
            };
            drawMenuList(g, items, menuCursor, 76);
            g.setColor(0x80A888);
            g.drawString("[2/8] MOVE   [5] SELECT", 38, VIEW_H + 14, Graphics.TOP | Graphics.LEFT);
        } else if (appState == APP_LEVEL_SELECT) {
            g.setColor(0x18221C);
            g.fillRect(24, 80, 192, 140);
            g.setColor(0x4A6A52);
            g.drawRect(24, 80, 192, 140);

            g.setColor(0xE0C850);
            g.drawString("SELECT SECTOR:", 68, 92, Graphics.TOP | Graphics.LEFT);

            g.setColor(0x70FF88);
            g.drawString("< SECTOR " + (levelSelectCursor + 1) + " / " + levelPaths.length + " >", 58, 126, Graphics.TOP | Graphics.LEFT);

            g.setColor(0x90B098);
            g.drawString("UNLOCKED: " + (unlockedLevelIdx + 1) + " OF " + levelPaths.length, 58, 156, Graphics.TOP | Graphics.LEFT);
            g.drawString("[5] LAUNCH   [0] BACK", 48, 190, Graphics.TOP | Graphics.LEFT);
        } else if (appState == APP_PAUSE_MENU) {
            String[] items = {
                "RESUME GAME",
                "RESTART SECTOR",
                "SOUND: " + (soundEnabled ? "ON" : "OFF"),
                "DETAIL: " + (lowDetail ? "2X TURBO" : "1X HIGH"),
                "MAIN MENU"
            };
            drawMenuList(g, items, menuCursor, 86);
            g.setColor(0x80A888);
            g.drawString("PAUSED - [5] SELECT", 52, VIEW_H + 14, Graphics.TOP | Graphics.LEFT);
        }
    }

    private void drawMenuList(Graphics g, String[] items, int cursor, int startY) {
        g.setFont(Font.getFont(Font.FACE_MONOSPACE, Font.STYLE_BOLD, Font.SIZE_SMALL));
        for (int i = 0; i < items.length; i++) {
            int iy = startY + i * 28;
            boolean sel = (i == cursor);
            g.setColor(sel ? 0x24482C : 0x141C16);
            g.fillRect(28, iy, 184, 23);
            g.setColor(sel ? 0x60EE78 : 0x384C3C);
            g.drawRect(28, iy, 184, 23);

            g.setColor(sel ? 0xFFFFFF : 0x98B8A0);
            g.drawString((sel ? "> " : "  ") + items[i], 36, iy + 5, Graphics.TOP | Graphics.LEFT);
        }
    }

    private void drawHud(Graphics g) {
        if (appState != APP_GAMEPLAY) {
            drawMenuOverlay(g);
            return;
        }

        int cx = SCREEN_W >> 1;
        int cy = VIEW_H >> 1;
        g.setColor(weaponTimer > 0 ? 0xFFCC00 : 0x30DF50);
        g.drawLine(cx - 4, cy, cx + 4, cy);
        g.drawLine(cx, cy - 4, cx, cy + 4);

        if (showMinimap) drawMinimap(g);

        g.setFont(Font.getFont(Font.FACE_MONOSPACE, Font.STYLE_BOLD, Font.SIZE_SMALL));

        if (bannerTimer > 0 && !levelCompleted && playerHp > 0) {
            g.setColor(0x182820);
            g.fillRect(45, 18, 150, 22);
            g.setColor(0x60DF70);
            g.drawRect(45, 18, 150, 22);
            g.drawString("SECTOR " + (currentLevelIdx + 1) + " / " + levelPaths.length, 66, 22, Graphics.TOP | Graphics.LEFT);
        }

        if (playerHp <= 0) {
            g.setColor(0x901010);
            g.fillRect(26, 110, 188, 44);
            g.setColor(0xFFFFFF);
            g.drawRect(26, 110, 188, 44);
            g.drawString("YOU DIED! [5] RETRY", 42, 125, Graphics.TOP | Graphics.LEFT);
        } else if (levelCompleted) {
            g.setColor(0x145224);
            g.fillRect(20, 100, 200, 56);
            g.setColor(0x80FF90);
            g.drawRect(20, 100, 200, 56);
            if (campaignCompleted) {
                g.drawString("BUNKER CLEARED!", 54, 110, Graphics.TOP | Graphics.LEFT);
                g.drawString("[5] MAIN MENU", 64, 132, Graphics.TOP | Graphics.LEFT);
            } else {
                g.drawString("SECTOR " + (currentLevelIdx + 1) + " COMPLETE!", 44, 110, Graphics.TOP | Graphics.LEFT);
                g.drawString("[5] ENTER SECTOR " + (currentLevelIdx + 2), 42, 132, Graphics.TOP | Graphics.LEFT);
            }
        }

        g.setColor(0x1E2420);
        g.fillRect(0, VIEW_H, SCREEN_W, HUD_H);
        g.setColor(0x4A5A4E);
        g.drawRect(0, VIEW_H, SCREEN_W - 1, HUD_H - 1);
        g.drawLine(82, VIEW_H, 82, SCREEN_H);
        g.drawLine(164, VIEW_H, 164, SCREEN_H);

        g.setColor(playerHp > 30 ? 0x88DD88 : 0xFF5050);
        g.drawString("HP: " + playerHp + "%", 6, VIEW_H + 6, Graphics.TOP | Graphics.LEFT);
        g.setColor(0x90B0A0);
        g.drawString("FOES: " + enemiesAlive, 6, VIEW_H + 24, Graphics.TOP | Graphics.LEFT);

        g.setColor(0xE0C040);
        g.drawString("AMMO: " + playerAmmo, 88, VIEW_H + 6, Graphics.TOP | Graphics.LEFT);
        g.drawString("LVL: " + (currentLevelIdx + 1) + "/" + levelPaths.length, 88, VIEW_H + 24, Graphics.TOP | Graphics.LEFT);

        g.setColor(0x60DF70);
        g.drawString("FPS: " + currentFps, 170, VIEW_H + 6, Graphics.TOP | Graphics.LEFT);
        g.drawString(lowDetail ? "RES: 2X" : "RES: 1X", 170, VIEW_H + 24, Graphics.TOP | Graphics.LEFT);
    }

    public void run() {
        Graphics g = getGraphics();
        long fpsTimer = System.currentTimeMillis();
        int frames = 0;

        while (running) {
            long frameStart = System.currentTimeMillis();

            updateLogic();
            render3D();

            int clipW = getWidth() < SCREEN_W ? getWidth() : SCREEN_W;
            int clipH = getHeight() < VIEW_H ? getHeight() : VIEW_H;
            g.drawRGB(frameBuffer, 0, SCREEN_W, 0, 0, clipW, clipH, false);
            drawHud(g);
            flushGraphics();

            frames++;
            long now = System.currentTimeMillis();
            if (now - fpsTimer >= 1000) {
                currentFps = frames;
                frames = 0;
                fpsTimer = now;
            }

            long elapsed = System.currentTimeMillis() - frameStart;
            if (elapsed < 33) {
                try {
                    Thread.sleep(33 - elapsed);
                } catch (InterruptedException e) {
                    break;
                }
            }
        }
    }
}
