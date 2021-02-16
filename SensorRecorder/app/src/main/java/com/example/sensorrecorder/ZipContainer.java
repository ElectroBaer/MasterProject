package com.example.sensorrecorder;

import java.io.IOException;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

public class ZipContainer extends OutputStreamContainer{
    public ZipOutputStream zipOutputStream;
    public String innerFileExtension;

    public ZipContainer(String name, String extension) throws IOException {
        super(name, "zip");
        innerFileExtension = extension;
    }

    public void OpenStream() throws IOException {
        if(isActive) {
            super.OpenStream();
            zipOutputStream = new ZipOutputStream(outputStream);
            zipOutputStream.putNextEntry(new ZipEntry(name + "." + innerFileExtension));
        }
    }

    public void WriteData(String data) throws IOException {
        if(isActive)
            zipOutputStream.write(data.getBytes());
    }

    public void Flush() throws IOException {
        if(isActive)
            zipOutputStream.flush();
    }

    public void Close() throws IOException {
        zipOutputStream.closeEntry();
        zipOutputStream.close();
        outputStream.close();
    }
}