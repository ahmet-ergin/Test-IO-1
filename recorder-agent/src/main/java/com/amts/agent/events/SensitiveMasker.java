package com.amts.agent.events;

import java.text.Normalizer;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Pattern;

/** Agent-side masking. The companion masks password fields first; the backend re-applies masking too. */
public final class SensitiveMasker {
    public static final String MASK = "[MASKED]";
    private static final Pattern OTP = Pattern.compile("\\d{4,8}");

    private SensitiveMasker() {
    }

    static String norm(String s) {
        if (s == null) return "";
        String lower = s.toLowerCase(new Locale("tr")).replace('ı', 'i');
        return Normalizer.normalize(lower, Normalizer.Form.NFD).replaceAll("\\p{M}", "");
    }

    public static boolean isSensitive(Map<String, Object> element, List<String> keywords) {
        if (element == null) return false;
        if (Boolean.TRUE.equals(element.get("password"))) return true;
        StringBuilder hay = new StringBuilder();
        for (String k : new String[]{"resourceId", "contentDesc", "hint", "accessibilityId"}) {
            Object v = element.get(k);
            if (v != null) hay.append(norm(v.toString())).append(' ');
        }
        String h = hay.toString();
        for (String kw : keywords) {
            String n = norm(kw);
            if (!n.isEmpty() && h.contains(n)) return true;
        }
        return false;
    }

    @SuppressWarnings("unchecked")
    public static void apply(Map<String, Object> event, List<String> keywords) {
        Map<String, Object> element = (Map<String, Object>) event.get("element");
        boolean sensitive = isSensitive(element, keywords);
        Map<String, Object> input = (Map<String, Object>) event.get("inputValue");
        if (input != null && input.get("value") != null) {
            String v = input.get("value").toString();
            if (sensitive || OTP.matcher(v.trim()).matches()) {
                Map<String, Object> masked = new LinkedHashMap<>();
                masked.put("masked", true);
                masked.put("value", null);
                masked.put("length", v.length());
                masked.put("reason", sensitive ? "SENSITIVE_FIELD" : "OTP_PATTERN");
                event.put("inputValue", masked);
            }
        }
        if (element != null && sensitive && element.get("text") != null) {
            element.put("text", MASK);
        }
    }

    public static List<int[]> sensitiveBounds(List<com.amts.agent.capture.HierarchyIndex.Node> nodes, List<String> keywords) {
        List<int[]> out = new ArrayList<>();
        for (com.amts.agent.capture.HierarchyIndex.Node n : nodes) {
            if (n.bounds != null && isSensitive(n.toElement(), keywords)) out.add(n.bounds);
        }
        return out;
    }
}
