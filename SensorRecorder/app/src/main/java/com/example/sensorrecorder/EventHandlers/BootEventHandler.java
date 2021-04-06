package com.example.sensorrecorder.EventHandlers;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import com.example.sensorrecorder.MainActivity;

public class BootEventHandler extends BroadcastReceiver {

    @Override
    public void onReceive(Context context, Intent intent) {
        if (Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) {
            Intent i = new Intent(context, MainActivity.class);
            i.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            context.startActivity(i);
        }
    }

}