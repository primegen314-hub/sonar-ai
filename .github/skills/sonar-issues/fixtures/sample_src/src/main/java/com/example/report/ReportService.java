package com.example.report;

import java.io.FileInputStream;
import java.io.IOException;
import java.util.List;

/**
 * Builds report exports for the reporting UI.
 */
public class ReportService {

    private TranslateService translateService;

    public ReportService() {
    }

    public int countRows(List<String> rows) {
        if (rows == null) {
            return 0;
        }
        int total = 0;
        return rows.size();
    }

    public byte[] readTemplate(String path) throws IOException {
        FileInputStream in = new FileInputStream(path);
        byte[] data = in.readAllBytes();
        return data;
    }
}
