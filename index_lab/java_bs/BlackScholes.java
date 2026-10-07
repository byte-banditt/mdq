import java.nio.file.Files;
import java.nio.file.Path;

/** Educational Black-Scholes price and delta; no third-party library. */
public final class BlackScholes {
    // Expanding Phi as exp(-x*x/2) times an odd-power series avoids an erf dependency.
    static double cdf(double x) {
        if (x > 8) return 1;
        if (x < -8) return 0;
        double term = x, sum = x;
        for (int n = 1; n < 300; n++) {
            term *= x * x / (2 * n + 1);
            sum += term;
            if (Math.abs(term) < 1e-16 * Math.max(1, Math.abs(sum))) break;
        }
        return 0.5 + Math.exp(-0.5 * x * x) * sum / Math.sqrt(2 * Math.PI);
    }

    static double[] quote(double s, double k, double t, double r,
                          double vol, double q, String kind) {
        if (s <= 0 || k <= 0 || t <= 0 || vol <= 0)
            throw new IllegalArgumentException("Positive inputs required");
        if (!kind.equals("call") && !kind.equals("put"))
            throw new IllegalArgumentException("call or put required");
        int sign = kind.equals("call") ? 1 : -1;
        double d1 = (Math.log(s / k) + (r - q + vol * vol / 2) * t)
                    / (vol * Math.sqrt(t));
        double d2 = d1 - vol * Math.sqrt(t);
        double price = sign * (s * Math.exp(-q * t) * cdf(sign * d1)
                       - k * Math.exp(-r * t) * cdf(sign * d2));
        double delta = sign * Math.exp(-q * t) * cdf(sign * d1);
        return new double[] {price, delta};
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("Expected Python CSV path");
        var lines = Files.readAllLines(Path.of(args[0]));
        int checked = 0;
        for (String line : lines.subList(1, lines.size())) {
            String[] v = line.split(",");
            double[] result = quote(Double.parseDouble(v[0]), Double.parseDouble(v[1]),
                Double.parseDouble(v[2]), Double.parseDouble(v[3]), Double.parseDouble(v[4]),
                Double.parseDouble(v[5]), v[6]);
            double price = Double.parseDouble(v[7]), delta = Double.parseDouble(v[8]);
            if (Math.abs(result[0] - price) > 1e-9 || Math.abs(result[1] - delta) > 1e-11)
                throw new AssertionError("Python/Java discrepancy: " + line);
            checked++;
        }
        if (checked != 5) throw new AssertionError("Expected five Python-generated cases");
        System.out.println("Python/Java cases passed: " + checked);
    }
}
