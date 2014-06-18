\copy (SELECT EXTRACT(month from edit_time) as mon, EXTRACT(year from edit_time) as yyyy, COUNT (DISTINCT user_id) AS "Active Users" FROM temp_edits WHERE user_id NOT IN (0,48) GROUP BY 2,1) TO '/home/jeremy/Programming/WeRelate/DataFiles/monthlyActive.csv' DELIMITER ',' HEADER CSV;
