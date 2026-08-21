package com.example.report;

import java.util.List;

/** Fixture caller so s05 can demonstrate usedBy (reverse-dependency) discovery. */
public class ReportController {

    private final ReportService reportService = new ReportService();

    public int rowCount(List<String> rows) {
        return reportService.countRows(rows);
    }
}
