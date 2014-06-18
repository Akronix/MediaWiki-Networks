\copy (SELECT EXTRACT(month from edit_time) as mon, EXTRACT(year from edit_time) as yyyy, COUNT(*) AS "Edits" FROM temp_edits WHERE user_id NOT IN (0,48) GROUP BY 1,2) to '/home/jeremy/Programming/WeRelate/DataFiles/MonthlyEdits.csv DELIMITER ',' CSV HEADER;