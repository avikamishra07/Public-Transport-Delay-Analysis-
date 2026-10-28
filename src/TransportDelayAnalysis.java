
import java.io.IOException;
import java.util.Iterator;

import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.fs.Path;
import org.apache.hadoop.io.LongWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Job;
import org.apache.hadoop.mapreduce.Mapper;
import org.apache.hadoop.mapreduce.Reducer;
import org.apache.hadoop.mapreduce.lib.input.FileInputFormat;
import org.apache.hadoop.mapreduce.lib.output.FileOutputFormat;
import org.apache.hadoop.util.Tool;
import org.apache.hadoop.util.ToolRunner;
import org.apache.hadoop.conf.Configured;

public class TransportDelayAnalysis extends Configured implements Tool {

    public static class DelayMapper
            extends Mapper<LongWritable, Text, Text, Text> {

        private final Text outputKey = new Text();
        private final Text outputValue = new Text();

        private String[] parseCSV(String line) {
            java.util.List<String> fields = new java.util.ArrayList<>();
            StringBuilder field = new StringBuilder();
            boolean quoted = false;

            for (int i = 0; i < line.length(); i++) {
                char c = line.charAt(i);

                if (c == '"') {
                    if (quoted && i + 1 < line.length()
                            && line.charAt(i + 1) == '"') {
                        field.append('"');
                        i++;
                    } else {
                        quoted = !quoted;
                    }
                } else if (c == ',' && !quoted) {
                    fields.add(field.toString());
                    field.setLength(0);
                } else {
                    field.append(c);
                }
            }

            fields.add(field.toString());
            return fields.toArray(new String[0]);
        }

        private void emit(Context context, String type, String group,
                          int delayed, double delay) throws IOException,
                          InterruptedException {
            outputKey.set(type + "|" + group);

            double delayedDelay = delayed == 1 ? delay : 0.0;
            outputValue.set("1," + delayed + "," + delay + ","
                    + delayedDelay);

            context.write(outputKey, outputValue);
        }

        @Override
        protected void map(LongWritable key, Text value, Context context)
                throws IOException, InterruptedException {

            String line = value.toString();

            if (line.startsWith("journey_id,")) {
                return;
            }

            String[] c = parseCSV(line);

            if (c.length < 45) {
                context.getCounter("Transport", "Malformed rows")
                        .increment(1);
                return;
            }

            try {
                String trainType = c[2].trim();
                int hour = Integer.parseInt(c[7].trim());
                String zone = c[13].trim();
                String cause = c[42].trim();

                double delay = Double.parseDouble(c[43].trim());
                int delayed = Integer.parseInt(c[44].trim());

                if (hour < 0 || hour > 23
                        || (delayed != 0 && delayed != 1)) {
                    context.getCounter("Transport", "Invalid rows")
                            .increment(1);
                    return;
                }

                if (!Double.isFinite(delay)) {
                    context.getCounter("Transport", "Invalid rows")
                            .increment(1);
                    return;
                }

                emit(context, "ZONE", zone, delayed, delay);
                emit(context, "TRAIN_TYPE", trainType, delayed, delay);
                emit(context, "DEPARTURE_HOUR",
                        String.format("%02d", hour), delayed, delay);
                emit(context, "DELAY_CAUSE", cause, delayed, delay);

                context.getCounter("Transport", "Processed rows")
                        .increment(1);

            } catch (Exception e) {
                context.getCounter("Transport", "Malformed rows")
                        .increment(1);
            }
        }
    }

    public static class DelayReducer
            extends Reducer<Text, Text, Text, Text> {

        @Override
        protected void reduce(Text key, Iterable<Text> values,
                              Context context) throws IOException,
                              InterruptedException {

            long journeys = 0;
            long delayedJourneys = 0;
            double totalDelay = 0.0;
            double delayedTotal = 0.0;

            for (Text value : values) {
                String[] parts = value.toString().split(",", -1);

                journeys += Long.parseLong(parts[0]);
                delayedJourneys += Long.parseLong(parts[1]);
                totalDelay += Double.parseDouble(parts[2]);
                delayedTotal += Double.parseDouble(parts[3]);
            }

            double delayRate = journeys == 0 ? 0.0
                    : 100.0 * delayedJourneys / journeys;

            double averageAll = journeys == 0 ? 0.0
                    : totalDelay / journeys;

            double averageDelayed = delayedJourneys == 0 ? 0.0
                    : delayedTotal / delayedJourneys;

            String result = journeys + "\t"
                    + delayedJourneys + "\t"
                    + String.format(java.util.Locale.US, "%.2f", delayRate)
                    + "\t"
                    + String.format(java.util.Locale.US, "%.2f", averageAll)
                    + "\t"
                    + String.format(java.util.Locale.US, "%.2f",
                                    averageDelayed);

            context.write(key, new Text(result));
        }
    }

    @Override
    public int run(String[] args) throws Exception {

        if (args.length != 2) {
            System.err.println(
                    "Usage: TransportDelayAnalysis <input> <output>");
            return 2;
        }

        Configuration conf = getConf();
        Job job = Job.getInstance(conf, "Public Transport Delay Analysis");

        job.setJarByClass(TransportDelayAnalysis.class);
        job.setMapperClass(DelayMapper.class);
        job.setReducerClass(DelayReducer.class);

        job.setMapOutputKeyClass(Text.class);
        job.setMapOutputValueClass(Text.class);
        job.setOutputKeyClass(Text.class);
        job.setOutputValueClass(Text.class);

        job.setNumReduceTasks(1);

        FileInputFormat.addInputPath(job, new Path(args[0]));
        FileOutputFormat.setOutputPath(job, new Path(args[1]));

        return job.waitForCompletion(true) ? 0 : 1;
    }

    public static void main(String[] args) throws Exception {
        int result = ToolRunner.run(
                new TransportDelayAnalysis(), args);
        System.exit(result);
    }
}
