package unifr.sensorrecorder.EventHandlers;

import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import java.io.IOException;

import unifr.sensorrecorder.DataContainer.StaticDataProvider;
import unifr.sensorrecorder.Evaluation.HandwashEvaluation;
import unifr.sensorrecorder.NotificationSpawner;
import unifr.sensorrecorder.SensorRecordingManager;

public class EvaluationReceiver extends BroadcastReceiver {

    public EvaluationReceiver(){

    }

    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent.getStringExtra("trigger") != null) {
            if (intent.getStringExtra("trigger").equals("handWashConfirm")) {
                if (SensorRecordingManager.isRunning) {
                    long timestamp = intent.getLongExtra("timestamp", -1);
                    if (timestamp > -1) {
                        StaticDataProvider.getProcessor().lastEvaluationTS = timestamp;
                        Intent startEvalIntent = new Intent(context, HandwashEvaluation.class);
                        startEvalIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
                        startEvalIntent.putExtra("timestamp", timestamp);
                        // startActivity(startEvalIntent);
                        PendingIntent resultPendingIntent = PendingIntent.getActivity(context, 12, startEvalIntent, PendingIntent.FLAG_UPDATE_CURRENT);
                        try {
                            resultPendingIntent.send();
                        } catch (PendingIntent.CanceledException e) {
                            e.printStackTrace();
                        }
                    }
                }
            }

            if (intent.getStringExtra("trigger").equals("handWashDecline")) {
                if (SensorRecordingManager.isRunning) {
                    long timestamp = intent.getLongExtra("timestamp", -1);
                    if (timestamp > -1) {
                        StaticDataProvider.getProcessor().lastEvaluationTS = timestamp;
                        try {
                            String line = timestamp + "\t" + 0 + "\n";
                            StaticDataProvider.getProcessor().writeEvaluation(line, false, 0);
                        } catch (IOException e) {
                            e.printStackTrace();
                        }
                    }
                }
                NotificationManager mNotificationManager = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
                mNotificationManager.cancel(NotificationSpawner.EVALUATION_REQUEST_CODE);

            }
            if (intent.getStringExtra("trigger").equals("close")) {
                long timestamp = intent.getLongExtra("timestamp", -1);
                if (timestamp > -1) {
                    StaticDataProvider.getProcessor().lastEvaluationTS = timestamp;
                    try {
                        String line = timestamp + "\t" + -1 + "\n";
                        StaticDataProvider.getProcessor().writeEvaluation(line, true, timestamp);
                    } catch (IOException e) {
                        e.printStackTrace();
                    }
                }
                NotificationManager mNotificationManager = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
                mNotificationManager.cancel(NotificationSpawner.EVALUATION_REQUEST_CODE);
            }
        }
    }
}
