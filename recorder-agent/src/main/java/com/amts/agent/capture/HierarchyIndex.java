package com.amts.agent.capture;

import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;

import javax.xml.parsers.DocumentBuilderFactory;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Indexed view of a uiautomator hierarchy dump. */
public class HierarchyIndex {
    private static final Pattern BOUNDS = Pattern.compile("\\[(-?\\d+),(-?\\d+)]\\[(-?\\d+),(-?\\d+)]");

    public static final class Node {
        public final Map<String, String> attrs;
        public final int[] bounds;

        Node(Map<String, String> attrs, int[] bounds) {
            this.attrs = attrs;
            this.bounds = bounds;
        }

        public boolean contains(int x, int y) {
            return bounds != null && x >= bounds[0] && x < bounds[2] && y >= bounds[1] && y < bounds[3];
        }

        long area() {
            return bounds == null ? Long.MAX_VALUE : (long) (bounds[2] - bounds[0]) * (bounds[3] - bounds[1]);
        }

        public Map<String, Object> toElement() {
            Map<String, Object> e = new LinkedHashMap<>();
            e.put("resourceId", blank(attrs.get("resource-id")));
            e.put("accessibilityId", blank(attrs.get("content-desc")));
            e.put("text", blank(attrs.get("text")));
            e.put("contentDesc", blank(attrs.get("content-desc")));
            e.put("hint", blank(attrs.get("hint")));
            e.put("className", blank(attrs.get("class")));
            e.put("bounds", bounds == null ? null : List.of(bounds[0], bounds[1], bounds[2], bounds[3]));
            e.put("clickable", "true".equals(attrs.get("clickable")));
            e.put("enabled", "true".equals(attrs.get("enabled")));
            e.put("password", "true".equals(attrs.get("password")));
            e.put("resolvedFrom", "HIERARCHY_SNAPSHOT");
            return e;
        }
    }

    public final List<Node> nodes = new ArrayList<>();
    public final String rootPackage;

    public HierarchyIndex(String xml) throws Exception {
        DocumentBuilderFactory f = DocumentBuilderFactory.newInstance();
        f.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        Document doc = f.newDocumentBuilder().parse(new ByteArrayInputStream(xml.getBytes(StandardCharsets.UTF_8)));
        NodeList list = doc.getElementsByTagName("node");
        String pkg = null;
        for (int i = 0; i < list.getLength(); i++) {
            Element el = (Element) list.item(i);
            Map<String, String> attrs = new LinkedHashMap<>();
            for (int a = 0; a < el.getAttributes().getLength(); a++) {
                attrs.put(el.getAttributes().item(a).getNodeName(), el.getAttributes().item(a).getNodeValue());
            }
            if (pkg == null) pkg = blank(attrs.get("package"));
            nodes.add(new Node(attrs, parseBounds(attrs.get("bounds"))));
        }
        this.rootPackage = pkg;
    }

    public static int[] parseBounds(String s) {
        if (s == null) return null;
        Matcher m = BOUNDS.matcher(s);
        if (!m.find()) return null;
        return new int[]{Integer.parseInt(m.group(1)), Integer.parseInt(m.group(2)),
                Integer.parseInt(m.group(3)), Integer.parseInt(m.group(4))};
    }

    /** Smallest clickable node containing the point; otherwise smallest node with identifying attributes. */
    public Node findAt(int x, int y) {
        Node bestClickable = null;
        Node bestAny = null;
        for (Node n : nodes) {
            if (!n.contains(x, y)) continue;
            if ("true".equals(n.attrs.get("clickable")) && (bestClickable == null || n.area() < bestClickable.area())) {
                bestClickable = n;
            }
            boolean identifiable = blank(n.attrs.get("resource-id")) != null || blank(n.attrs.get("text")) != null
                    || blank(n.attrs.get("content-desc")) != null;
            if (identifiable && (bestAny == null || n.area() < bestAny.area())) bestAny = n;
        }
        return bestClickable != null ? bestClickable : bestAny;
    }

    /** Hash of structure only (class + resource-id), so typing text does not count as a screen change. */
    public String structuralHash() throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-1");
        for (Node n : nodes) {
            md.update((n.attrs.getOrDefault("class", "") + "|" + n.attrs.getOrDefault("resource-id", "") + ";")
                    .getBytes(StandardCharsets.UTF_8));
        }
        StringBuilder sb = new StringBuilder();
        for (byte b : md.digest()) sb.append(String.format("%02x", b));
        return sb.toString();
    }

    static String blank(String s) {
        return s == null || s.isEmpty() ? null : s;
    }
}
