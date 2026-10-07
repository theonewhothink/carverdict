import test from 'node:test';import assert from 'node:assert/strict';import {filterCars,modelLink} from './catalogue-core.mjs';
const rows=[{n:'Citroën 2CV',b:'Citroën',p:'2cv.jpg',y:'1948',u:'/library/citroen/2cv/'},{n:'Toyota RAV4',b:'Toyota',p:'rav.jpg',y:'1994',u:'/library/toyota/toyota-rav4/'},{n:'Toyota forgotten prototype',b:'Toyota',p:'',y:'',u:'/library/toyota/#model'}];
test('complete catalogue search includes unphotographed and undated entries',()=>{assert.equal(filterCars(rows,{query:'toyota'}).length,2);assert.equal(filterCars(rows,{query:'citroen 2cv'}).length,1);assert.equal(filterCars(rows,{query:'rav4 toyota'}).length,1);assert.equal(filterCars(rows,{query:'invented'}).length,0);});
test('filters preserve unknown years and photo gaps rather than inventing metadata',()=>{assert.equal(filterCars(rows,{brand:'Toyota',photos:true}).length,1);assert.equal(filterCars(rows,{era:'1940'})[0].n,'Citroën 2CV');assert.equal(filterCars(rows,{era:'1990'}).length,1);assert.equal(modelLink({u:'javascript:bad()'}),'/library/');});

import {suggestCars} from './catalogue-core.mjs';
test('autocomplete ranks exact models, tolerates punctuation and includes entries without photos',()=>{
 const rows=[{n:'Mazda MX-5',b:'Mazda',u:'/library/mazda/mx5/',p:'photo'},{n:'Mazda MX-5 RF',b:'Mazda',u:'/library/mazda/rf/',p:''},{n:'Citroën DS',b:'Citroën',u:'/library/citroen/ds/',p:''}];
 assert.equal(suggestCars(rows,'mx5')[0].n,'Mazda MX-5');assert.equal(suggestCars(rows,'citroen')[0].n,'Citroën DS');assert.equal(suggestCars(rows,'x').length,0);assert.equal(suggestCars([...rows,rows[0]],'mazda').length,2);
});
import {photoUrl} from './catalogue-core.mjs';
test('photo delivery uses checked exceptions and encoded direct thumbnails without dropping references',()=>{
 assert.equal(photoUrl({p:'Lost.jpg',e:'unavailable'}),'');
 assert.equal(photoUrl({p:'Old.jpg',t:'https://upload.wikimedia.org/resolved.jpg'}),'https://upload.wikimedia.org/resolved.jpg');
 assert.equal(photoUrl({p:'Original.jpg',t:'older',it:'scoped'}),'scoped');
 assert.match(photoUrl({p:"Car's #1.jpg",h:'ab'}),/\/a\/ab\/Car's_%231\.jpg\/960px-Car's_%231\.jpg$/);
});
test('typing compact model names works in both autocomplete and full results',()=>{
 const cars=[{n:'Mazda MX-5',b:'Mazda',p:'image',u:'/library/mazda/mx5/',f:0},{n:'Honda CR-V',b:'Honda',p:'image',u:'/library/honda/crv/'}];
 assert.equal(filterCars(cars,{query:'mx5'})[0].n,'Mazda MX-5');
 assert.equal(filterCars(cars,{query:'crv'})[0].n,'Honda CR-V');
 assert.equal(suggestCars([{n:'Ferrari P',b:'Ferrari',p:'image',u:'/p/'},{n:'Ferrari F40',b:'Ferrari',p:'image',u:'/f40/',f:0}],'ferrari')[0].n,'Ferrari F40');
});
test('non-Latin model names remain searchable instead of turning into an empty query',()=>{
 const cars=[{n:'ЗИЛ 111',b:'ЗИЛ',p:'image',u:'/library/zil/111/'},{n:'Toyota RAV4',b:'Toyota',p:'image',u:'/library/toyota/rav4/'}];
 assert.equal(filterCars(cars,{query:'ЗИЛ'}).length,1);assert.equal(suggestCars(cars,'зил')[0].n,'ЗИЛ 111');
 assert.equal(filterCars(cars,{query:'несуществующий'}).length,0);
});
