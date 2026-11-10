/* Discovery categories inferred from catalog subject terms and journal titles. */
window.journalFields = {
 'Electrical and Computer Engineering': {'Hardware computing and architecture':'hardware|architectur|vlsi|computer.aided|integrated circuit|solid.state|microelectronic|neuromorphic|memory|computing systems','Circuits and electronics':'circuit|electronic|semiconductor|electron device|microelectronic','Algorithms and artificial intelligence':'algorithm|artificial intelligence|neural|neurocomput|machine learning|pattern|intelligent|computation','Signals and communications':'signal|communication|wireless|antenna|telecommunication|network','Photonics and optics':'optic|photonic|laser|lightwave','Control and robotics':'control|robot|automation|cybernetic','Power and energy':'power|energy|electric|renewable'},
 'Computer Science': {'Algorithms and theory':'algorithm|theoretic|computation|mathematic','AI and data science':'intelligence|learning|neural|data|pattern|neurocomput','Software and systems':'software|programming|systems|distributed|computing|architecture','Security and networks':'security|cryptograph|network|privacy'},
 'Physical Sciences': {'Physics':'physics|physical|quantum','Chemistry':'chemistr|chemical|cataly','Materials':'material|polymer|nano|metallurg'},
 'Life Sciences and Medicine': {'Medicine and healthcare':'medic|clinical|health|surg|disease|oncolog|cardio|nurs','Biology and neuroscience':'biolog|neurosci|genetic|cell|biochem|microbi|ecolog'},
 'Engineering': {'Mechanical and manufacturing':'mechanic|manufactur|thermal|fluid|aerospace','Civil and environment':'civil|construction|environment|water|structur','Chemical engineering':'chemical engineering|process|cataly'},
 'Social Sciences and Business': {'Economics and business':'econom|business|finance|management|account','Psychology and education':'psycholog|education|learning|behavio','Humanities and society':'social|humanit|history|language|law|politic'}
};
window.journalSubjectMatch = function(journal, field, area) {
 if (!field) return true;
 const text = journal.title + ' ' + (journal.subjects || []).join(' ');
 const areas = window.journalFields[field];
 return new RegExp(area ? areas[area] : Object.values(areas).join('|'), 'i').test(text);
};
