#!/usr/bin/env bash
set -e

CLDC_JAR="lib/microemu-cldc-2.0.4.jar"
MIDP_JAR="lib/microemu-midp-2.0.4.jar"
LANG_STUB_JAR="lib/cldc-lang-stub.jar"
PROGUARD_JAR="lib/proguard-base-6.2.2.jar"
MICROEMU_JAR="lib/microemulator-2.0.4.jar"

mkdir -p lib build dist res
rm -f lib/mmapi-stub.jar

# 1. Завантаження J2ME бібліотек і ProGuard
if [ ! -s "$CLDC_JAR" ]; then
    echo "[*] Downloading CLDC 1.1 API..."
    curl -fL "https://repo1.maven.org/maven2/org/microemu/microemu-cldc/2.0.4/microemu-cldc-2.0.4.jar" -o "$CLDC_JAR"
fi

if [ ! -s "$MIDP_JAR" ]; then
    echo "[*] Downloading MIDP 2.0 API..."
    curl -fL "https://repo1.maven.org/maven2/org/microemu/microemu-midp/2.0.4/microemu-midp-2.0.4.jar" -o "$MIDP_JAR"
fi

if [ ! -s "$PROGUARD_JAR" ]; then
    echo "[*] Downloading ProGuard (J2ME Preverifier)..."
    curl -fL "https://repo1.maven.org/maven2/net/sf/proguard/proguard-base/6.2.2/proguard-base-6.2.2.jar" -o "$PROGUARD_JAR"
fi

if [ ! -s "$MICROEMU_JAR" ]; then
    echo "[*] Downloading MicroEmulator..."
    curl -fL "https://repo1.maven.org/maven2/org/microemu/microemulator/2.0.4/microemulator-2.0.4.jar" -o "$MICROEMU_JAR"
fi

# 2. Експорт базових класів java.lang.* та java.io.* у формат Java 8 (class version 52.0) для ProGuard
if [ ! -s "$LANG_STUB_JAR" ]; then
    echo "[*] Building standalone CLDC java.lang/java.io bridge for OpenJDK 25..."
    mkdir -p build/j2me_rt
    python3 - << 'EOF'
import zipfile, subprocess, os

# Витягуємо список базових класів CLDC та компілюємо чистий міст з --release 8
helper_src = "build/j2me_rt/ExtractRt.java"
with open(helper_src, "w") as f:
    f.write("""
import java.io.*;
import java.net.URI;
import java.nio.file.*;
import java.util.*;
import java.util.zip.*;

public class ExtractRt {
    public static void main(String[] args) throws Exception {
        FileSystem fs = FileSystems.getFileSystem(URI.create("jrt:/"));
        String[] pkgs = {"java/lang", "java/io", "java/util"};
        try (ZipOutputStream zos = new ZipOutputStream(new FileOutputStream(args[0]))) {
            for (String pkg : pkgs) {
                Path p = fs.getPath("/modules/java.base/" + pkg);
                if (!Files.exists(p)) continue;
                try (DirectoryStream<Path> stream = Files.newDirectoryStream(p, "*.class")) {
                    for (Path entry : stream) {
                        String name = pkg + "/" + entry.getFileName().toString();
                        if (name.endsWith("module-info.class")) continue;
                        byte[] bytes = Files.readAllBytes(entry);
                        // Понижуємо магічну версію class-файлу заголовка до Java 8 (52.0) для читання ієрархії в ProGuard
                        bytes[4] = 0; bytes[5] = 0; bytes[6] = 0; bytes[7] = 52;
                        zos.putNextEntry(new ZipEntry(name));
                        zos.write(bytes);
                        zos.closeEntry();
                    }
                }
            }
        }
    }
}
""")
subprocess.run(["javac", helper_src], check=True)
subprocess.run(["java", "-cp", "build/j2me_rt", "ExtractRt", "lib/cldc-lang-stub.jar"], check=True)
EOF
    rm -rf build/j2me_rt
fi

# 3. Генерація/імпорт PNG-текстур, WAV-звуків та пакування рівнів (.pak + .b3d)
echo "[*] Packing PNG assets and level data..."
python3 tools/build_resources.py

# 4. Компіляція вихідного коду J2ME (--release 8 генерує чистий байт-код без bootstrap-попереджень)
echo "[*] Compiling J2ME sources..."
rm -rf build/*
javac --release 8 \
    -classpath "$CLDC_JAR:$MIDP_JAR" \
    -d build src/bunker3d/*.java

# 5. Пакування чорнового JAR
cp res/* build/
jar cfm dist/raw.jar MANIFEST.MF -C build .

# 6. Преверифікація під CLDC 1.1 (-microedition) та даунгрейд байт-коду до Java 1.3
echo "[*] Preverifying bytecode for Nokia S40 (CLDC 1.1)..."
java -jar "$PROGUARD_JAR" @proguard.cfg \
    -injars dist/raw.jar \
    -outjars dist/Bunker3D.jar \
    -libraryjars "$MIDP_JAR:$CLDC_JAR:$LANG_STUB_JAR" \
    -dontnote "**" \
    -dontwarn "**"
rm -f dist/raw.jar

# 7. Генерація .jad файлу
JAR_SIZE=$(stat -c%s "dist/Bunker3D.jar")
cat > dist/Bunker3D.jad <<EOF
MIDlet-1: Bunker3D, , bunker3d.BunkerMIDlet
MIDlet-Jar-Size: ${JAR_SIZE}
MIDlet-Jar-URL: Bunker3D.jar
MIDlet-Name: Bunker 3D Engine
MIDlet-Vendor: DmytroDev
MIDlet-Version: 0.1.0
MicroEdition-Configuration: CLDC-1.1
MicroEdition-Profile: MIDP-2.0
Nokia-MIDlet-Original-Display-Size: 240,320
Nokia-MIDlet-Target-Display-Size: 240,320
EOF

echo "=========================================="
echo "[SUCCESS] Built dist/Bunker3D.jar (${JAR_SIZE} bytes)"
echo "=========================================="

# Запуск емулятора при передачі --run
if [ "$1" == "--run" ]; then
    export _JAVA_AWT_WM_NONREPARENTING=1
    export DISPLAY="${DISPLAY:-:0}"
    java -Djava.awt.headless=false -jar "$MICROEMU_JAR" \
        --resizableDevice 240 320 \
        dist/Bunker3D.jad
fi
